"""Person C — strategist agent.

Per generation we hand the builders one improvement question per
category in ``CATEGORIES_USED``. For each category we make a single LLM
call that sees the current champion source plus a curated pool of seed
ideas for that category, and asks the model to return one concrete,
implementable improvement direction grounded in the champion's gaps.

The seed pools (``QUESTION_POOLS``) are not throwaway — they're baked
into each per-category prompt as worked examples so the model has
strong priors on what "a good question for this category" looks like,
and as a deterministic fallback when the LLM call fails (no API key,
network error, empty response). The fallback uses the rotation logic
that the prior deterministic version of this file used: advance the
pool pointer by generation number, plus one extra step for every past
generation in which this category produced the champion. That keeps
behavior sensible in tests and offline.

All ``len(CATEGORIES_USED)`` LLM calls run in parallel via
``asyncio.gather`` so total wall-clock is one round-trip, not N.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from pathlib import Path

from darwin.config import settings
from darwin.llm import complete_text

logger = logging.getLogger("darwin.agents.strategist")

CATEGORIES = [
    "prompt",
    "search",
    "book",
    "evaluation",
    "sampling",
    "time_management",
    "quiescence",
    "pruning",
    "endgame",
    "move_ordering",
    "evaluation_tuning",
]

# Pure-code engines have no LLM-prompt component, so "prompt" is dropped
# from the active rotation. The remaining categories all map cleanly to
# classical chess-engine techniques.
CATEGORIES_USED = [
    "search",
    "evaluation",
    "book",
    "sampling",
    "time_management",
    "quiescence",
    "pruning",
    "endgame",
    "move_ordering",
    "evaluation_tuning",
]

# How many categories to actually run per generation. Each active
# category produces one strategist question, one builder, one adversary
# critique, and one fixer pass — so this is also the cohort size before
# validation drops failing candidates. Less than ``len(CATEGORIES_USED)``
# means we sample: the active set is chosen by ``_select_active_categories``
# (exploit winners + explore the rest in a sliding window) rather than
# running every category every gen.
ACTIVE_PER_GEN = 4


# Each pool holds multiple concrete improvement directions. We pick by
# ``(gen_number - 1) % len(pool)`` so the same pool produces a new
# direction every generation until it cycles. Pool sizes are different
# across categories — that's fine; each rotates independently.
QUESTION_POOLS: dict[str, list[str]] = {
    "search": [
        "Add iterative deepening up to depth 4. Start at depth 1, "
        "deepen until ~50% of the move budget is spent, return the "
        "best move found at the deepest completed iteration.",
        "Implement principal-variation search (PVS) on top of alpha-"
        "beta. Search the first move full-window, the rest with a "
        "null window, re-search if the null-window result raises "
        "alpha.",
        "Add a transposition table keyed by board.fen() (or zobrist "
        "hash if you prefer). Each entry stores (depth, score, "
        "flag). Probe at the top of the search; cut off on exact "
        "score at the same depth or better.",
        "Add MVV-LVA (most-valuable-victim, least-valuable-attacker) "
        "move ordering for captures, then the rest by material gain. "
        "Better ordering means more alpha-beta cutoffs at the same "
        "depth.",
        "Implement late-move reductions: search the first 4 moves "
        "full depth, the rest with depth-1 first, only re-search "
        "full-depth if the reduced search beats alpha.",
    ],
    "evaluation": [
        "Add a piece-square table for each piece type (knight in "
        "the center > knight on the edge, bishop on long diagonals, "
        "etc.). Keep the table small — 64 entries per piece type, "
        "tuned by intuition rather than learning.",
        "Add a king-safety penalty: count attacker pieces near each "
        "king's square (within Chebyshev distance 2) and subtract a "
        "weighted penalty from the side under attack.",
        "Add a pawn-structure term: penalize doubled pawns, "
        "isolated pawns, and bonus for passed pawns (a pawn whose "
        "advance is not blocked by enemy pawns on adjacent files).",
        "Add a mobility term: count legal moves for each side after "
        "the position is reached, weight at ~10 cp per extra move "
        "for the side to move.",
        "Add a center-control bonus: each piece attacking d4/d5/e4/"
        "e5 contributes +5 cp to its side. Encourages early central "
        "presence.",
    ],
    "book": [
        "Hardcode a small opening book (~10 lines) of common "
        "responses by FEN-prefix. e.g. e4 → e5 / c5 / e6, etc. If "
        "the position matches a book entry, play the book move; "
        "otherwise fall through to your search code.",
        "Add a 'best response' table for the most common ~20 "
        "starting positions after move 1. Lookup by FEN, fall "
        "through to search if no match.",
        "Implement opening principles as soft heuristics in the "
        "first 8 plies: prefer central pawn moves, prefer "
        "developing minor pieces over moving the same piece twice, "
        "prefer king-side castling.",
        "Build an endgame mate-pattern recognizer for K+R vs K and "
        "K+Q vs K. When the position matches, drive the lone king "
        "to the edge using simple distance heuristics rather than "
        "search.",
    ],
    "sampling": [
        "Monte Carlo Tree Search (light): for each legal root move, "
        "play 20 random rollouts to a fixed ply depth, score by "
        "material at the end of each rollout, pick the move with "
        "the best average score.",
        "Random move sampling with eval filter: generate 10 random "
        "candidate moves, evaluate the resulting position with your "
        "eval function, pick the highest-scoring.",
        "Stochastic best-first: at each node in your search, try "
        "moves in a random order rather than legal-moves order. "
        "Reduces alpha-beta efficiency but expands the search space.",
        "Multi-armed-bandit move selection: track for each move a "
        "running average of its score across the search; bias future "
        "exploration toward high-mean / high-uncertainty moves "
        "(simple UCB1 formula).",
    ],
    "time_management": [
        "Add aspiration windows around the previous iteration's "
        "score: search with [score-50, score+50] first, only "
        "re-search with a full window on a fail-high or fail-low. "
        "Cuts work in stable positions.",
        "Implement soft and hard time limits: target ~5% of the "
        "remaining clock per move (soft), abort the search at 2x "
        "soft (hard). On a fail-high mid-iteration, finish the "
        "current move before stopping.",
        "Add a panic extension: if the side to move is in check, or "
        "the previous move was a recapture in a hot exchange, grant "
        "an extra 50% of the move's time budget before returning.",
        "Allocate the move budget by game phase: spend more time on "
        "moves 10-30 (middlegame), less on book-like opening moves "
        "(1-8) and forced endgame moves where one side has K+R or "
        "less.",
        "Implement easy-move detection: if iteration depth N returns "
        "the same best move as depth N-1 with a score within 30 cp, "
        "stop searching early and return — the move is unlikely to "
        "change with more depth.",
    ],
    "quiescence": [
        "Add capture-only quiescence search: at depth 0 of the main "
        "search, instead of returning the static eval, recursively "
        "search captures until a quiet position is reached. Cap at "
        "quiescence depth 4 to prevent runaway.",
        "Add check-evasion quiescence: at quiescence nodes, also "
        "consider all legal moves (not just captures) when the side "
        "to move is in check. Without this, quiescence misses forced "
        "mate sequences at the horizon.",
        "Add delta pruning to quiescence: skip a capture if the "
        "captured-piece value plus a 200 cp safety margin still "
        "can't raise the side-to-move's score above alpha. Avoids "
        "wasting time on hopeless captures.",
        "Add static exchange evaluation (SEE) to filter quiescence "
        "captures: only search captures where SEE >= 0. Skips "
        "obviously losing captures (e.g. queen takes defended pawn) "
        "without searching them.",
        "Implement recapture-only quiescence at deeper plies: in the "
        "first 2 ply of quiescence, search all captures; deeper than "
        "that, only consider moves that recapture on the square the "
        "opponent just moved to. Sharp focus, very cheap.",
    ],
    "pruning": [
        "Add null-move pruning: at non-PV nodes with depth >= 3 and "
        "the side to move not in check, give the opponent a free "
        "move and search to depth-3. If the result still beats beta, "
        "prune the entire subtree. Skip in pawn endgames (zugzwang).",
        "Add futility pruning at frontier nodes (depth == 1): if the "
        "static eval plus a 150 cp margin is below alpha, skip "
        "non-capture, non-check moves. They're unlikely to raise "
        "alpha at this depth.",
        "Add razoring near leaves: at depth <= 2, if static eval "
        "plus a 300 cp margin is below alpha, drop directly into "
        "quiescence instead of searching the full depth.",
        "Add the history heuristic: track for each (from, to) square "
        "pair how often a quiet move at that pair caused a beta "
        "cutoff. Use the score to order quiet moves after captures "
        "and killers.",
        "Add killer-move tables: for each ply, remember the last 2 "
        "quiet moves that caused a beta cutoff. When ordering moves "
        "at the same ply later, try those killers right after "
        "captures — they often cut again.",
    ],
    "endgame": [
        "Add bishop-pair and opposite-color-bishop awareness: bonus "
        "of +30 cp for keeping both bishops; in endings with one "
        "bishop each on opposite colors and few pawns, scale eval "
        "toward 0 (drawish).",
        "Add 'rook behind passed pawn' bonus: a rook on the same "
        "file as a passed pawn, on the side away from the pawn's "
        "promotion square, gets +20 cp. Classic Tarrasch rule.",
        "Add king activation in pawn endgames: when only pawns and "
        "kings remain, weight the king's distance to the center / "
        "to the most advanced passed pawn heavily (~10 cp per "
        "Chebyshev step closer).",
        "Add 50-move and insufficient-material draw detection in "
        "the eval: if halfmove clock > 80 or material is K vs K, "
        "K+B vs K, K+N vs K, return 0 immediately rather than "
        "computing a misleading material score.",
        "Add KPK and KBN-K mate heuristics: when the position "
        "matches one of these patterns, drive the lone king to the "
        "edge / corner using a precomputed distance-to-corner "
        "table rather than relying on search to find mate.",
    ],
    "move_ordering": [
        "Order moves at every node as: (1) PV move from the previous "
        "iteration, (2) hash move from the transposition table, (3) "
        "captures by MVV-LVA, (4) killers, (5) quiet moves by "
        "history-heuristic score. Single biggest multiplier on "
        "alpha-beta efficiency.",
        "Add the counter-move heuristic: track, for each opponent "
        "move, the quiet move that most often refuted it. When the "
        "opponent plays move X, try its counter-move first among "
        "quiets.",
        "Implement static exchange evaluation (SEE) for capture "
        "ordering: order captures by SEE score (highest first) "
        "rather than MVV-LVA. More accurate for trades on defended "
        "squares.",
        "Add an internal iterative deepening fallback: at PV nodes "
        "with no hash move, do a shallow (depth-2) search first to "
        "produce a best-move guess, then use it to order the "
        "full-depth search.",
        "Bias root-move ordering by previous iteration's score: at "
        "the root, sort moves by the score they achieved last "
        "iteration (best first). Keeps the PV stable across "
        "iterations and finds re-searches faster.",
    ],
    "evaluation_tuning": [
        "Implement tapered eval: keep two piece-square tables per "
        "piece (midgame, endgame) and interpolate between them by "
        "a phase value derived from remaining non-pawn material. "
        "Knights get more central in the midgame, kings more active "
        "in the endgame.",
        "Re-balance piece values by phase: knights worth +20 cp in "
        "closed positions (>= 14 pawns on the board), bishops worth "
        "+20 cp in open positions (<= 10 pawns). Same code, "
        "different weights.",
        "Add a tempo bonus: +10 cp for the side to move. Small but "
        "consistent — it represents the right to play first in the "
        "current position.",
        "Scale eval toward 0 in drawish material configurations: "
        "K+B vs K+B same color, K+N vs K+N, K+R vs K+R with no "
        "pawns. Multiply the computed eval by 0.25 in those cases "
        "rather than reporting full material advantage.",
        "Add a contempt factor: subtract a small constant (e.g. 20 "
        "cp) from any score that's within 50 cp of 0. Discourages "
        "the engine from accepting draws when the position is "
        "objectively level — useful against weaker opponents.",
    ],
}


@dataclass
class Question:
    index: int
    category: str
    text: str


# Loaded for back-compat — older orchestrator code paths inspect this.
PROMPT = (Path(__file__).parent / "prompts" / "strategist_v1.md").read_text()


# One short description per category, included in the per-category LLM
# prompt so the model knows what "this category" actually scopes to.
CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "search": (
        "alpha-beta search enhancements — iterative deepening, PVS, "
        "transposition tables, search shape (not pruning, not move ordering)"
    ),
    "evaluation": (
        "static evaluation terms — adding new positional features the eval "
        "function considers (not re-tuning existing weights)"
    ),
    "book": (
        "opening-book lookups, opening principles in the first 8 plies, "
        "or known mating patterns that bypass search in solved positions"
    ),
    "sampling": (
        "stochastic move-selection methods — Monte Carlo rollouts, random "
        "sampling with eval filter, bandit-style exploration"
    ),
    "time_management": (
        "how the engine allocates its move budget — aspiration windows, "
        "soft/hard time limits, panic extensions, easy-move detection"
    ),
    "quiescence": (
        "extending search past the horizon for tactical positions — "
        "capture-only quiescence, check evasions, delta pruning, SEE filtering"
    ),
    "pruning": (
        "soft cutoffs distinct from pure alpha-beta — null-move pruning, "
        "futility pruning, razoring, history heuristic, killer moves"
    ),
    "endgame": (
        "phase-specific endgame play — bishop-pair awareness, rook-behind-"
        "passed-pawn, king activation, draw detection, KPK / KBN-K patterns"
    ),
    "move_ordering": (
        "the order in which moves are tried before search runs — PV move, "
        "TT hash move, MVV-LVA, killers, history, counter-moves, SEE ordering"
    ),
    "evaluation_tuning": (
        "calibrating existing eval weights rather than adding new terms — "
        "tapered eval, phase-dependent piece values, tempo, draw scaling, contempt"
    ),
}


def _select_active_categories(
    generation_number: int,
    champion_wins_per_category: dict[str, int],
) -> list[str]:
    """Pick ``ACTIVE_PER_GEN`` categories uniformly at random, no replacement.

    No coverage guarantee, no exploit/explore split, no determinism by
    gen number — each call is an independent draw from the unseeded
    global ``random`` state. Some categories will be tried often, some
    rarely; that's by design. The two arguments are kept on the
    signature for API compatibility but ignored here.
    """
    del generation_number, champion_wins_per_category  # unused, kept for API
    if ACTIVE_PER_GEN >= len(CATEGORIES_USED):
        return list(CATEGORIES_USED)
    return random.sample(CATEGORIES_USED, ACTIVE_PER_GEN)


def _deterministic_pick(
    category: str,
    generation_number: int,
    champion_wins_per_category: dict[str, int],
) -> str:
    """Fallback pool entry when the LLM call can't produce a question.

    Mirrors the rotation rule from the prior deterministic strategist:
    advance by generation number, plus one extra step per past gen in
    which this category produced the champion.
    """
    pool = QUESTION_POOLS[category]
    rotation = (generation_number - 1) + champion_wins_per_category.get(category, 0)
    return pool[rotation % len(pool)]


def _build_category_prompt(
    category: str,
    champion_code: str,
    history: list[dict],
    runner_up_code: str | None,
    champion_question: dict | None,
) -> tuple[str, str]:
    """Build (system, user) for one category's LLM call.

    The seed pool is included verbatim as worked examples — the model
    can pick one, adapt one, or invent its own as long as it stays in
    scope for ``category``.
    """
    seeds = "\n".join(f"  - {seed}" for seed in QUESTION_POOLS[category])
    description = CATEGORY_DESCRIPTIONS.get(category, category)

    system = (
        "You are the strategist for a self-improving classical chess engine. "
        "Your job is to propose ONE concrete improvement to the current "
        "champion's source code, scoped strictly to a single category."
    )

    history_lines: list[str] = []
    for h in history[-5:]:
        gen = h.get("generation", "?")
        cat = h.get("champion_category") or "(retained)"
        history_lines.append(f"  - gen {gen}: champion came from category {cat}")
    history_block = "\n".join(history_lines) if history_lines else "  (no prior generations)"

    champ_q_text = "(none)"
    if champion_question:
        champ_q_text = (
            f"category={champion_question.get('category')!r} "
            f"text={champion_question.get('text')!r}"
        )

    runner_up_block = (
        f"```python\n{runner_up_code}\n```" if runner_up_code else "(none)"
    )

    user = f"""Category: **{category}** — {description}

Seed ideas for this category (use as inspiration, pick one verbatim, \
adapt one, or invent your own — but stay strictly in scope for this \
category):

{seeds}

CURRENT CHAMPION SOURCE:

```python
{champion_code}
```

CHAMPION'S ORIGINATING QUESTION (the strategist question whose answer \
produced the source above):

{champ_q_text}

PREVIOUS-GEN RUNNER-UP SOURCE:

{runner_up_block}

RECENT HISTORY (last 5 gens):
{history_block}

Output: a single paragraph (3-6 sentences) describing one concrete, \
implementable change in the **{category}** category. The builder will \
implement this in ~50 lines of Python (stdlib + python-chess only). \
Prefer something the champion does NOT already do. Plain English, no \
JSON, no preamble, no headers — just the paragraph."""

    return system, user


async def _propose_one(
    index: int,
    category: str,
    champion_code: str,
    history: list[dict],
    runner_up_code: str | None,
    champion_question: dict | None,
    generation_number: int,
    champion_wins_per_category: dict[str, int],
) -> Question:
    """LLM call for one category, with deterministic fallback on failure."""
    system, user = _build_category_prompt(
        category=category,
        champion_code=champion_code,
        history=history,
        runner_up_code=runner_up_code,
        champion_question=champion_question,
    )
    try:
        text = await complete_text(
            model=settings.strategist_model,
            system=system,
            user=user,
            max_tokens=400,
            provider=settings.provider_for("strategist"),
        )
        text = (text or "").strip()
        if len(text) < 20:
            raise ValueError(f"strategist returned too-short text ({len(text)} chars)")
    except Exception as exc:
        logger.warning(
            "strategist LLM call for category=%s failed, falling back to seed pool: %s",
            category, exc,
        )
        text = _deterministic_pick(category, generation_number, champion_wins_per_category)

    return Question(index=index, category=category, text=text)


async def propose_questions(
    champion_code: str,
    history: list[dict],
    runner_up_code: str | None = None,
    champion_question: dict | None = None,
    generation_number: int | None = None,
) -> list[Question]:
    """Return one improvement question per active category this gen.

    Each generation runs ``ACTIVE_PER_GEN`` categories rather than the
    full ``CATEGORIES_USED`` list — see ``_select_active_categories``.
    For each active category we run an LLM call in parallel. The LLM
    sees the champion source, recent history, and the category's seed
    pool as worked examples, and returns one concrete improvement
    direction scoped to that category. On any failure (no API key,
    network error, empty response, exception) we fall back to a
    deterministic pick from the seed pool using rotation by gen number.

    Args:
        champion_code: source of the current champion engine.
        history: list of prior gen records. Each record is a dict with
            optional ``generation`` (int) and ``champion_category``
            (str). Used both to bias the deterministic-fallback rotation
            toward winning categories and to anchor the LLM in context.
        runner_up_code: source of last gen's runner-up, also competing
            this gen — useful as a contrasting example for the LLM.
        champion_question: the strategist question that produced the
            champion source, included in the per-category prompt.
        generation_number: explicit gen number. If omitted, derived
            from ``len(history) + 1``. Lets the orchestrator be
            authoritative about gen number even with empty history.
    """
    if generation_number is None:
        generation_number = max(1, len(history) + 1)

    champion_wins_per_category: dict[str, int] = {c: 0 for c in CATEGORIES_USED}
    for h in history:
        cat = h.get("champion_category")
        if cat in champion_wins_per_category:
            champion_wins_per_category[cat] += 1

    active = _select_active_categories(generation_number, champion_wins_per_category)
    logger.info(
        "propose_questions gen=%d active=%s (%d of %d)",
        generation_number, active, len(active), len(CATEGORIES_USED),
    )

    tasks = [
        _propose_one(
            index=i,
            category=cat,
            champion_code=champion_code,
            history=history,
            runner_up_code=runner_up_code,
            champion_question=champion_question,
            generation_number=generation_number,
            champion_wins_per_category=champion_wins_per_category,
        )
        for i, cat in enumerate(active)
    ]
    return await asyncio.gather(*tasks)
