"""STUB — Person B owns. Plays one game between two engines.

Handles legal-move check, time control, max-move cap, error adjudication,
and PGN serialization. Emits game.move and game.finished events as it goes.
See plans/person-b-tournament.md.
"""

from dataclasses import dataclass

from cubist.engines.base import Engine


@dataclass
class GameResult:
    white: str
    black: str
    result: str  # "1-0" | "0-1" | "1/2-1/2"
    termination: str  # "checkmate" | "stalemate" | "time" | "max_moves" | "error"
    pgn: str


async def play_game(white: Engine, black: Engine, time_per_move_ms: int) -> GameResult:
    raise NotImplementedError("Person B: implement game loop.")
