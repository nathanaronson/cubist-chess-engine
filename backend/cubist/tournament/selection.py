"""Champion selection.

Each generation's tournament produces a ``Standings`` with per-engine
score (wins + 0.5*draws). We rank everyone by overall score, break ties
randomly, and the #1 becomes the new champion. The previous head-to-head
gate ("candidate must beat incumbent in their direct subset") was
discarded — with 4 candidates per cohort and only 2 head-to-head games
per pair, that gate had high enough variance to lock the demo on
baseline indefinitely. Overall score across the whole round-robin is a
more stable signal.

``select_top_n`` returns the top N engines (default 2) so the orchestrator
can carry the runner-up forward as a second incumbent in the next gen —
giving the strategist+builder more genetic diversity to work with.
"""

import random

from cubist.engines.base import Engine
from cubist.tournament.runner import Standings


def _ranked_engines(
    standings: Standings, engines: list[Engine]
) -> list[Engine]:
    """Sort engines by score descending, with random tiebreak."""
    # `random.random()` per key call is the standard "shuffle ties" trick.
    # The negative score makes desc-order via the natural ascending sort.
    return sorted(
        engines,
        key=lambda e: (-standings.scores.get(e.name, 0.0), random.random()),
    )


def select_champion(
    standings: Standings,
    incumbent: Engine,
    candidates: list[Engine],
) -> tuple[Engine, bool]:
    """Returns ``(new_champion, promoted)``.

    Highest overall score wins; ties are resolved randomly (so a flat
    "everyone got 50%" round still picks someone). ``promoted`` is True
    iff the winner is not the incumbent.
    """
    if not candidates:
        return incumbent, False
    ranked = _ranked_engines(standings, [incumbent, *candidates])
    winner = ranked[0]
    return winner, winner.name != incumbent.name


def select_top_n(
    standings: Standings,
    incumbent: Engine,
    candidates: list[Engine],
    n: int = 2,
) -> list[Engine]:
    """Return the top-N engines by score across ``[incumbent, *candidates]``.

    The first element is the new champion; subsequent elements are the
    runners-up that the orchestrator will carry into the next generation
    as additional incumbents. ``n`` defaults to 2 because the demo loop
    benchmarks "top-2 forward" — bumping it higher widens the round-
    robin quadratically (engines × games_per_pairing) and is rarely
    worth it.
    """
    pool = [incumbent, *candidates]
    if not pool:
        return []
    ranked = _ranked_engines(standings, pool)
    return ranked[: max(1, n)]
