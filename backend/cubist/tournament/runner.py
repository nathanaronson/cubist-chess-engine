"""Round-robin scheduler with bounded parallel game execution.

Runs both colors per pairing, but caps concurrent games with
`settings.max_parallel_games`. This keeps slow or rate-limited LLM providers
from turning every tournament game into a timeout at once.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Awaitable, Callable

from cubist.config import settings
from cubist.engines.base import Engine
from cubist.tournament.referee import GameResult, play_game

EventCb = Callable[[dict], Awaitable[None]] | None


@dataclass
class Standings:
    scores: dict[str, float]  # engine name -> total points
    games: list[GameResult]


async def round_robin(
    engines: list[Engine],
    games_per_pairing: int,
    time_per_move_ms: int,
    on_event: EventCb = None,
) -> Standings:
    if games_per_pairing < 0:
        raise ValueError("games_per_pairing must be non-negative")
    if settings.max_parallel_games < 1:
        raise ValueError("max_parallel_games must be at least 1")

    pairings = []
    game_id = 0
    for i, white in enumerate(engines):
        for j, black in enumerate(engines):
            if i == j:
                continue
            for _ in range(games_per_pairing):
                pairings.append((white, black, game_id))
                game_id += 1

    sem = asyncio.Semaphore(settings.max_parallel_games)

    async def _guarded(white: Engine, black: Engine, game_id: int) -> GameResult:
        async with sem:
            return await play_game(white, black, time_per_move_ms, on_event, game_id)

    results = await asyncio.gather(*[_guarded(white, black, gid) for white, black, gid in pairings])
    scores: dict[str, float] = defaultdict(float)
    for result in results:
        if result.result == "1-0":
            scores[result.white] += 1.0
        elif result.result == "0-1":
            scores[result.black] += 1.0
        else:
            scores[result.white] += 0.5
            scores[result.black] += 0.5

    for engine in engines:
        scores.setdefault(engine.name, 0.0)

    return Standings(scores=dict(scores), games=results)
