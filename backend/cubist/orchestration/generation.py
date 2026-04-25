"""The big loop: one generation end-to-end.

strategist -> 2 builders (parallel) -> validator -> tournament -> selection
-> persist + emit events.
"""

import asyncio
import inspect
import json
import logging
from datetime import datetime

from cubist.agents.builder import build_engine, validate_engine
from cubist.agents.strategist import propose_questions
from cubist.api.websocket import bus
from cubist.config import settings
from cubist.engines.base import Engine
from cubist.engines.registry import load_engine
from cubist.storage.db import get_session
from cubist.storage.models import EngineRow, GameRow, GenerationRow
from cubist.tournament.runner import round_robin
from cubist.tournament.selection import select_champion

log = logging.getLogger("cubist.orchestration")


def _read_source(engine: Engine) -> str:
    return inspect.getsource(type(engine))


async def run_generation(champion: Engine, generation_number: int) -> Engine:
    await bus.emit(
        {
            "type": "generation.started",
            "number": generation_number,
            "champion": champion.name,
        }
    )

    questions = await propose_questions(_read_source(champion), [])
    for q in questions:
        await bus.emit(
            {
                "type": "strategist.question",
                "index": q.index,
                "category": q.category,
                "text": q.text,
            }
        )

    paths = await asyncio.gather(
        *[
            build_engine(_read_source(champion), champion.name, generation_number, q)
            for q in questions
        ],
        return_exceptions=True,
    )

    candidates: list[Engine] = []
    candidate_paths: dict[str, str] = {}
    for q, p in zip(questions, paths):
        if isinstance(p, Exception):
            log.error(
                "build_engine raised q=%d category=%s err=%r",
                q.index, q.category, p,
            )
            await bus.emit(
                {
                    "type": "builder.completed",
                    "question_index": q.index,
                    "engine_name": "-",
                    "ok": False,
                    "error": str(p),
                }
            )
            continue
        ok, err = await validate_engine(p)
        name = p.stem
        if not ok:
            log.error(
                "validator rejected q=%d category=%s engine=%s reason=%r",
                q.index, q.category, name, err,
            )
        else:
            log.info("validator accepted q=%d category=%s engine=%s", q.index, q.category, name)
        await bus.emit(
            {
                "type": "builder.completed",
                "question_index": q.index,
                "engine_name": name,
                "ok": ok,
                "error": err,
            }
        )
        if ok:
            eng = load_engine(str(p))
            candidate_paths[eng.name] = str(p.resolve())
            candidates.append(eng)

    # If every candidate fell through, ``round_robin([champion])`` will
    # schedule zero games (i==j filter). Surface this loudly so the
    # operator knows why the dashboard goes silent after builder events.
    if not candidates:
        log.error(
            "generation %d has 0 candidates — every builder failed or "
            "was rejected by the validator. Tournament will schedule 0 games. "
            "Check engines/generated/_failures/ for raw model responses.",
            generation_number,
        )

    standings = await round_robin(
        [champion, *candidates],
        games_per_pairing=settings.games_per_pairing,
        time_per_move_ms=settings.time_per_move_ms,
        on_event=bus.emit,
    )
    new_champion, promoted = select_champion(standings, champion, candidates)

    with get_session() as s:
        gen_row = GenerationRow(
            number=generation_number,
            champion_before=champion.name,
            champion_after=new_champion.name,
            strategist_questions_json=json.dumps(
                [{"category": q.category, "text": q.text} for q in questions]
            ),
            finished_at=datetime.utcnow(),
        )
        s.add(gen_row)
        for g in standings.games:
            s.add(
                GameRow(
                    generation=generation_number,
                    white_name=g.white,
                    black_name=g.black,
                    pgn=g.pgn,
                    result=g.result,
                    termination=g.termination,
                )
            )
        if promoted:
            existing = s.get(EngineRow, new_champion.name)
            if existing is None:
                from sqlmodel import select

                existing = s.exec(
                    select(EngineRow).where(EngineRow.name == new_champion.name)
                ).first()
            if existing is None:
                s.add(
                    EngineRow(
                        name=new_champion.name,
                        generation=generation_number,
                        parent_name=champion.name,
                        code_path=candidate_paths[new_champion.name],
                    )
                )
        s.commit()

    await bus.emit(
        {
            "type": "generation.finished",
            "number": generation_number,
            "new_champion": new_champion.name,
            "elo_delta": 0.0,
            "promoted": promoted,
        }
    )
    return new_champion


async def run_generation_task() -> None:
    """Triggered by the API. Loads current champion from DB, runs one generation.

    Wrapped in a top-level try/except so a crash in any sub-step is logged
    with a full traceback AND surfaced to the UI via a terminal
    ``generation.finished`` event (``promoted=False``). Without this the
    asyncio Task just dies, the dashboard hangs on "running", and we have
    to grep honcho's stdout to find out what went wrong.

    ``asyncio.CancelledError`` is treated specially: a ``generation.cancelled``
    event is emitted before the cancellation propagates, so the frontend
    can clear its in-progress panels.
    """
    with get_session() as s:
        from sqlmodel import select

        last = s.exec(
            select(GenerationRow).order_by(GenerationRow.number.desc())
        ).first()
        next_number = (last.number + 1) if last else 1

        if last is None:
            from cubist.engines.baseline import engine as champion
        else:
            row = s.exec(
                select(EngineRow).where(EngineRow.name == last.champion_after)
            ).first()
            if row is None:
                # baseline won the last generation — no EngineRow was inserted for it
                from cubist.engines.baseline import engine as champion
            else:
                champion = load_engine(row.code_path)

    log.info("run_generation_task starting generation=%d", next_number)
    try:
        await run_generation(champion, next_number)
        log.info("run_generation_task finished generation=%d", next_number)
    except asyncio.CancelledError:
        log.warning("run_generation_task cancelled generation=%d", next_number)
        # Emit a terminal event so the dashboard knows to stop showing
        # "Waiting for strategist…" / live-board placeholders. We swallow
        # any error from the bus emit (rare, but the queue may be torn
        # down at server-shutdown time) so cancellation always propagates.
        try:
            await bus.emit(
                {"type": "generation.cancelled", "number": next_number}
            )
        except Exception:  # pragma: no cover — best-effort emit
            pass
        raise
    except Exception:
        log.exception("run_generation_task crashed generation=%d", next_number)
        await bus.emit(
            {
                "type": "generation.finished",
                "number": next_number,
                "new_champion": champion.name,
                "elo_delta": 0.0,
                "promoted": False,
            }
        )


# ---------------------------------------------------------------------------
# Cancellation API — used by /api/generations/run (replace) and
# /api/generations/stop (cancel only).
# ---------------------------------------------------------------------------

# Module-level handle to the currently-running generation task, if any.
# Single-process / single-worker assumption: this matches the deploy setup
# (uvicorn with one worker; honcho composes one backend process).
_current_task: asyncio.Task[None] | None = None
_task_lock = asyncio.Lock()


async def _await_cancellation(task: asyncio.Task[None]) -> None:
    """Await a cancelled task, swallowing the standard cancellation exception.

    Useful so the caller doesn't need its own try/except around
    ``await task`` after ``task.cancel()``.
    """
    try:
        await task
    except (asyncio.CancelledError, Exception):
        # Cancelled is the expected path; any other exception is already
        # logged by the task's own try/except. No re-raise here — we
        # specifically want to ignore cancellation cleanup errors.
        pass


async def start_or_replace_generation_task() -> None:
    """Cancel any in-flight generation, then start a new one.

    Mounted to ``POST /api/generations/run``. Two clicks of the dashboard's
    Run button no longer race each other — the second click cancels the
    first generation cleanly (emits ``generation.cancelled``) before
    starting the second.
    """
    global _current_task
    async with _task_lock:
        if _current_task is not None and not _current_task.done():
            log.info("preempting in-flight generation task before starting new one")
            _current_task.cancel()
            await _await_cancellation(_current_task)
        _current_task = asyncio.create_task(run_generation_task())


async def stop_current_generation_task() -> bool:
    """Cancel the in-flight generation, if any.

    Mounted to ``POST /api/generations/stop`` and called by the frontend's
    ``beforeunload`` ``sendBeacon`` on page reload. Returns ``True`` if a
    task was cancelled, ``False`` if there was nothing to cancel — the
    endpoint surfaces this as ``{"stopped": bool}`` so the dashboard's
    Stop button can grey out when there's nothing running.
    """
    global _current_task
    if _current_task is None or _current_task.done():
        return False
    _current_task.cancel()
    await _await_cancellation(_current_task)
    return True
