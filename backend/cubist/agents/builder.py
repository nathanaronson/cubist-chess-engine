"""STUB — Person C owns. The builder agent.

Takes a question + the champion's source; emits a Python module under
engines/generated/ that exposes a top-level `engine` satisfying Engine.
See plans/person-c-agents.md.
"""

from pathlib import Path

from cubist.agents.strategist import Question


async def build_engine(
    champion_code: str,
    champion_name: str,
    generation: int,
    question: Question,
) -> Path:
    """Generate engine source, write to generated/, return its path.

    Raises on syntax error or builder failure. Validation (smoke game)
    happens in agents/validator.py."""
    raise NotImplementedError("Person C: implement builder agent.")


async def validate_engine(module_path: Path) -> tuple[bool, str | None]:
    """Smoke-test: load the engine and play one game vs random. Return (ok, err)."""
    raise NotImplementedError("Person C: implement validator.")
