"""STUB — Person E owns. The big loop: one generation end-to-end.

strategist -> 5 builders (parallel) -> validator -> tournament -> selection
-> persist + emit events. See plans/person-e-infra.md.
"""

from cubist.engines.base import Engine


async def run_generation(champion: Engine, generation_number: int) -> Engine:
    raise NotImplementedError("Person E: orchestrate one generation end-to-end.")
