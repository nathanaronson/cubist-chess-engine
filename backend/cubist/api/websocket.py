"""FROZEN CONTRACT — do not change without team sync.

WebSocket event payloads. Backend (Person E) emits these; frontend
(Person D) consumes them. Mirror in `frontend/src/api/events.ts` MUST
stay in sync.
"""

from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field


class GenerationStarted(BaseModel):
    type: Literal["generation.started"] = "generation.started"
    number: int
    champion: str


class StrategistQuestion(BaseModel):
    type: Literal["strategist.question"] = "strategist.question"
    index: int  # 0..4
    category: str  # "prompt" | "search" | "book" | "evaluation" | "sampling"
    text: str


class BuilderCompleted(BaseModel):
    type: Literal["builder.completed"] = "builder.completed"
    question_index: int
    engine_name: str
    ok: bool
    error: str | None = None


class GameMove(BaseModel):
    type: Literal["game.move"] = "game.move"
    game_id: int
    fen: str
    san: str
    white: str
    black: str
    ply: int


class GameFinished(BaseModel):
    type: Literal["game.finished"] = "game.finished"
    game_id: int
    result: str  # "1-0" | "0-1" | "1/2-1/2"
    termination: str
    pgn: str
    white: str
    black: str


class GenerationFinished(BaseModel):
    type: Literal["generation.finished"] = "generation.finished"
    number: int
    new_champion: str
    elo_delta: float
    promoted: bool  # True if a new champion was crowned


Event = Union[
    GenerationStarted,
    StrategistQuestion,
    BuilderCompleted,
    GameMove,
    GameFinished,
    GenerationFinished,
]


class Envelope(BaseModel):
    """All WS messages are wrapped in this envelope."""

    event: Event = Field(discriminator="type")
