"""STUB — Person B owns. Anti-regression gate.

The top scorer in the tournament becomes the new champion ONLY IF it beats
the prior champion in their head-to-head subset. Otherwise champion persists.
"""

from cubist.engines.base import Engine
from cubist.tournament.runner import Standings


def select_champion(
    standings: Standings,
    incumbent: Engine,
    candidates: list[Engine],
) -> tuple[Engine, bool]:
    """Returns (new_champion, promoted). promoted=False means incumbent persisted."""
    raise NotImplementedError("Person B: implement anti-regression selection.")
