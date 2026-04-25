"""STUB — Person A owns. The generation-0 engine.

Implement BaselineEngine: prompts the player LLM with the FEN + legal moves,
parses the SAN response, returns a chess.Move. See plans/person-a-engine-core.md.
"""

import chess

from cubist.engines.base import BaseLLMEngine


class BaselineEngine(BaseLLMEngine):
    def __init__(self) -> None:
        super().__init__(name="baseline-v0", generation=0, lineage=[])

    async def select_move(
        self,
        board: chess.Board,
        time_remaining_ms: int,
    ) -> chess.Move:
        raise NotImplementedError("Person A: implement baseline LLM move selection.")


engine = BaselineEngine()
