"""STUB — Person C owns. The strategist agent.

Given the current champion + history, produce 5 distinct improvement
questions spanning categories: prompt, search, book, evaluation, sampling.
See plans/person-c-agents.md.
"""

from dataclasses import dataclass


@dataclass
class Question:
    index: int
    category: str
    text: str


async def propose_questions(
    champion_code: str,
    history: list[dict],
) -> list[Question]:
    """Call Opus; return exactly 5 questions across distinct categories."""
    raise NotImplementedError("Person C: implement strategist agent.")
