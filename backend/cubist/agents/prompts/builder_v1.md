You are a chess engine builder. Modify the champion source below to
answer ONE specific improvement question.

QUESTION (category={category}):
{question_text}

CHAMPION SOURCE:

```python
{champion_code}
```

REQUIREMENTS

  - Subclass `BaseLLMEngine` from `cubist.engines.base`. Builder-generated
    engines may also implement the `Engine` Protocol directly, but
    subclassing is simpler.
  - The class `__init__` MUST call:
        super().__init__(
            name="{engine_name}",
            generation={generation},
            lineage=["{champion_name}"],
        )
  - Implement `async def select_move(self, board, time_remaining_ms)`
    returning a `chess.Move` that is legal on `board`.
  - The module MUST end with the literal line: `engine = YourEngineClass()`
    (the registry imports this top-level symbol).
  - Stay under 100 lines of code total.
  - Imports: use exactly the four lines in the "Imports (MUST copy
    verbatim)" section below — plus stdlib (random, math, time,
    asyncio, …) only as needed. Anything else — `subprocess`,
    `os.system`, `socket`, `eval`, `exec`, `importlib`, network
    libraries — is forbidden and will be rejected by a regex backstop.
  - Always have a fallback that returns a legal move, even if the LLM
    response is malformed. The engine MUST NOT raise during a game.
    The standard fallback is `next(iter(board.legal_moves))`.
  - Keep the answer focused on the question's category — don't pile on
    orthogonal changes. One concept per builder run.

## Imports (MUST copy verbatim)

Use exactly these imports — no others, no aliasing:

    import chess
    from cubist.engines.base import BaseLLMEngine
    from cubist.llm import complete_text
    from cubist.config import settings

NEVER write any of these — they import the module, not the
``Settings()`` instance inside it, so every access to
``settings.player_model`` raises ``AttributeError`` and the engine
silently falls back to the first legal move forever:

    from cubist import config as settings        # WRONG
    import cubist.config as settings             # WRONG

The validator rejects engines containing those patterns.

Then read model IDs and time budgets off the instance:

    text = await complete_text(settings.player_model, system, user, max_tokens=10)

## Output

Submit the entire module source as a single string via the
`submit_engine` tool.
