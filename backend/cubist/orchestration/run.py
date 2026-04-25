"""STUB — Person E owns. CLI entrypoint: run N generations end-to-end.

Usage: uv run python -m cubist.orchestration.run --generations 3
"""

import argparse
import asyncio


async def main(generations: int) -> None:
    raise NotImplementedError("Person E: wire run_generation into a loop.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=int, default=1)
    args = parser.parse_args()
    asyncio.run(main(args.generations))
