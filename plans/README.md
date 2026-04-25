# Build Plans

Each engineer takes one plan and one branch. Read your own plan in full, then skim the other four so you know who you depend on and who depends on you.

| Plan | Branch | Owner |
|---|---|---|
| [Engine core & baseline](./person-a-engine-core.md) | `feat/engine-core` | A |
| [Tournament & referee](./person-b-tournament.md) | `feat/tournament` | B |
| [Agents (strategist + builder)](./person-c-agents.md) | `feat/agents` | C |
| [Frontend dashboard](./person-d-frontend.md) | `feat/frontend` | D |
| [Infra, API, orchestration, demo](./person-e-infra.md) | `feat/infra` | E |

## Frozen contracts

These three files define how the workstreams integrate. **Do not change them without paging the team.**

- `backend/cubist/engines/base.py` — Engine Protocol
- `backend/cubist/storage/models.py` — SQLite schema
- `backend/cubist/api/websocket.py` + `frontend/src/api/events.ts` — WS event payloads

## Merge order (deadlines from kickoff)

1. **Hour 6** — Person A merges `feat/engine-core`. Unblocks B and C.
2. **Hour 9** — Person B merges `feat/tournament`. Unblocks E's full orchestration.
3. **Hour 10** — Person C merges `feat/agents`. Unblocks E's real generation runs.
4. **Hour 12** — Person E merges `feat/infra`. Unblocks D's switch from mocks to live.
5. **Hour 16** — Person D merges `feat/frontend`. Demo-ready.

Hours 16–24 are eval, polish, demo rehearsal, sleep.
