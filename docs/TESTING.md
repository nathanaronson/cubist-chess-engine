# Testing

State of the test suite as of this branch. No prescriptions — current state only.

## What is tested

All tests live under [backend/tests/](../backend/tests/) and run via `pytest`.

| Test file | Covers |
|---|---|
| [test_baseline.py](../backend/tests/test_baseline.py) | `baseline-v0` engine returns legal moves, finds mate-in-one, prefers winning material. |
| [test_builder.py](../backend/tests/test_builder.py) | `darwin.agents.builder` validation regex, forbidden-import gate, and the `build_engine` flow with a mocked LLM. |
| [test_elo.py](../backend/tests/test_elo.py) | Elo math: expected score, K-factor updates, batch ratings update from game results. |
| [test_orchestration.py](../backend/tests/test_orchestration.py) | `darwin.orchestration.generation.run_generation_task` against an in-memory SQLite DB. |
| [test_referee.py](../backend/tests/test_referee.py) | `play_game`: two random engines finish; illegal moves and engine exceptions are handled per game. |
| [test_registry.py](../backend/tests/test_registry.py) | `load_engine` resolves dotted paths, loads from file, and rejects modules without an `engine` symbol. |
| [test_runner.py](../backend/tests/test_runner.py) | Local `round_robin` produces the expected number of games and scores sum correctly. |
| [test_selection.py](../backend/tests/test_selection.py) | `select_champion` / `select_top_n` against synthetic standings. |
| [test_strategist.py](../backend/tests/test_strategist.py) | Deterministic strategist returns 4 distinct-category questions and rotates per generation. |

## What is NOT tested

- WebSocket bus and HTTP routes — [darwin.api](../backend/darwin/api/) has no tests.
- Storage layer — [darwin.storage.db](../backend/darwin/storage/db.py) and [models](../backend/darwin/storage/models.py) are exercised only indirectly through the orchestration test.
- LLM client — [darwin.llm](../backend/darwin/llm.py) is mocked everywhere; no unit tests for the real wrapper.
- Modal dispatch path — [darwin.tournament.modal_runner](../backend/darwin/tournament/modal_runner.py) has no tests; `test_runner.py` force-pins the local backend.
- Frontend — no unit tests in [frontend/](../frontend/); CI relies on `tsc && vite build` to catch type / build errors.

## How to run

```bash
make test         # uv run pytest -q (backend only)
make lint         # uv run ruff check .
make check        # lint + test
make check-docs   # verify markdown links and darwin.* symbol references
make ci           # lint + format-check + test + check-docs (matches CI)
```

## How CI runs it

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs three jobs in parallel on `ubuntu-latest`:

1. **backend** — `uv sync --extra dev`, `ruff check`, `ruff format --check`, `pytest -q`.
2. **frontend** — `npm ci && npm run build` (build runs `tsc` first).
3. **docs** — `python scripts/check_docs.py`.
