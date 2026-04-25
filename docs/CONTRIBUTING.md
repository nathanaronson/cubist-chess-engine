# Contributing

## Branch naming

- Feature work: `feat/<scope>` (e.g. `feat/agents`, `feat/tournament`).
- Follow-ups / fixes: `followup/<scope>` or `fix/<scope>`.
- Docs/process: `docs/<scope>` or `chore/<scope>`.

One branch, one workstream. Don't overlap with another branch's scope — see [PROCESS.md](PROCESS.md) for ownership.

## Commit style

- Conventional prefix: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`.
- Subject ≤72 chars, imperative mood, lowercase.
- Body explains *why*, not *what* — the diff already shows the what.

## The `make check` gate

Run before opening a PR:

```bash
make check     # ruff lint + pytest
```

`make check` is the pre-PR contract. Don't push if it's red.

## Running tests

```bash
make test                                  # full pytest suite
cd backend && uv run pytest tests/test_referee.py -v   # one file
cd backend && uv run pytest -k tournament -v           # by keyword
```

Tests live in [backend/tests/](../backend/tests/). They use `RandomEngine` so nothing burns LLM API budget.

## Adding a new engine

Engines satisfy the `Engine` Protocol in [backend/darwin/engines/base.py](../backend/darwin/engines/base.py) — a frozen contract.

1. Add a module under [backend/darwin/engines/](../backend/darwin/engines/) with a top-level `engine` symbol.
2. Subclass `BaseLLMEngine` (LLM-backed) or implement `Engine` directly.
3. Always include a fallback to a legal move so an LLM error never crashes a game.
4. Add a test in [backend/tests/](../backend/tests/) loading via `darwin.engines.registry.load_engine`.

Builder-generated engines are written to `engines/generated/` at runtime by the agent; you do not check them in.

## Adding a new WebSocket event

WS events are a frozen contract — they cross the backend/frontend boundary.

1. Add the Pydantic model to [backend/darwin/api/websocket.py](../backend/darwin/api/websocket.py) and include it in the `Event` discriminated union.
2. Mirror the type in [frontend/src/api/events.ts](../frontend/src/api/events.ts) — the discriminator is `event.type`.
3. Update consumers under [frontend/src/components/](../frontend/src/components/) to handle the new variant.
4. Coordinate the change — both files must merge together. Page the team before splitting them across PRs.

## What not to do

- Don't modify a frozen contract file in passing — see [ARCHITECTURE.md](ARCHITECTURE.md#frozen-contracts).
- Don't import the Anthropic or Google SDK directly. Always go through `darwin.llm.complete*` so we have one rate-limit choke point.
- Don't commit `backend/darwin/engines/generated/*.py` — they're builder output, not source.
- Don't push `backend/darwin.db` — it's local SQLite state.
