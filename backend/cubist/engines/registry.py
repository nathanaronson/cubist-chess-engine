"""STUB — Person A owns. Dynamic engine loading.

Loads engines from `engines/` (built-in) and `engines/generated/` (builder
output). Each module must expose a top-level `engine` symbol satisfying
the Engine Protocol.
"""

from pathlib import Path

from cubist.engines.base import Engine

GENERATED_DIR = Path(__file__).parent / "generated"


def load_engine(module_path: str) -> Engine:
    """Import a module by dotted path or file path; return its `engine` symbol."""
    raise NotImplementedError("Person A: implement dynamic import + Protocol check.")


def list_generated() -> list[Path]:
    return sorted(GENERATED_DIR.glob("*.py"))
