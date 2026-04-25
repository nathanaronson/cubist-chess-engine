"""STUB — Person B owns. Round-robin scheduler with parallel game execution.

Runs all pairings concurrently via asyncio.gather. Both colors per pairing.
Returns a scoreboard. See plans/person-b-tournament.md.
"""

from dataclasses import dataclass

from cubist.engines.base import Engine
from cubist.tournament.referee import GameResult


@dataclass
class Standings:
    scores: dict[str, float]  # engine name -> total points
    games: list[GameResult]


async def round_robin(
    engines: list[Engine],
    games_per_pairing: int,
    time_per_move_ms: int,
) -> Standings:
    raise NotImplementedError("Person B: implement parallel round-robin.")
