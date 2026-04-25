"""Tests for darwin.agents.strategist.

The strategist samples ``ACTIVE_PER_GEN`` categories from
``CATEGORIES_USED`` and runs one LLM call per active category, falling
back to a deterministic seed-pool pick on any failure. These tests
force the fallback path by stubbing ``complete_text`` to raise, so they
remain hermetic — no API keys, no network.
"""

from __future__ import annotations

import pytest

from darwin.agents import strategist
from darwin.agents.strategist import (
    ACTIVE_PER_GEN,
    CATEGORIES_USED,
    QUESTION_POOLS,
    Question,
    _select_active_categories,
    propose_questions,
)


@pytest.fixture(autouse=True)
def _force_fallback(monkeypatch):
    """Make every LLM call raise so all tests exercise the fallback path."""

    async def _boom(*args, **kwargs):
        raise RuntimeError("LLM disabled in tests")

    monkeypatch.setattr(strategist, "complete_text", _boom)


@pytest.mark.asyncio
async def test_propose_questions_returns_active_subset():
    qs = await propose_questions(champion_code="x = 1", history=[])

    assert len(qs) == ACTIVE_PER_GEN
    categories = [q.category for q in qs]
    assert len(set(categories)) == ACTIVE_PER_GEN
    assert set(categories).issubset(set(CATEGORIES_USED))
    assert all(isinstance(q, Question) for q in qs)
    assert all(len(q.text) >= 20 for q in qs)


@pytest.mark.asyncio
async def test_fallback_text_rotates_with_history_length(monkeypatch):
    """Within-category rotation still advances by gen number on the
    fallback path. Active-set sampling is forced to a fixed cohort
    here so we can compare the SAME category across two gens — the
    rotation we care about is the seed-pool index, not which set of
    categories happens to be active."""
    fixed = ["search", "evaluation", "book", "endgame"]
    monkeypatch.setattr(strategist, "_select_active_categories", lambda *a, **kw: list(fixed))

    qs1 = await propose_questions(champion_code="x = 1", history=[])
    qs2 = await propose_questions(
        champion_code="x = 1", history=[{"generation": 1}]
    )

    cat_to_text_1 = {q.category: q.text for q in qs1}
    cat_to_text_2 = {q.category: q.text for q in qs2}
    movable = [c for c in fixed if len(QUESTION_POOLS[c]) > 1]
    assert movable, "expected at least one fixed category with a multi-entry pool"
    for cat in movable:
        assert cat_to_text_1[cat] != cat_to_text_2[cat], (
            f"category {cat} did not rotate between gen 1 and gen 2"
        )


@pytest.mark.asyncio
async def test_propose_questions_accepts_optional_kwargs(monkeypatch):
    """Optional kwargs flow through without error. With the active set
    pinned, the fallback path produces identical output with or without
    the extra kwargs (which are ignored on the fallback path)."""
    fixed = ["search", "evaluation", "book", "endgame"]
    monkeypatch.setattr(strategist, "_select_active_categories", lambda *a, **kw: list(fixed))

    qs_no_extras = await propose_questions(champion_code="x = 1", history=[])
    qs_with_extras = await propose_questions(
        champion_code="x = 1",
        history=[],
        runner_up_code="y = 2",
        champion_question={"category": "search", "text": "old question"},
    )

    assert [q.text for q in qs_no_extras] == [q.text for q in qs_with_extras]


@pytest.mark.asyncio
async def test_propose_questions_index_field_is_unique():
    qs = await propose_questions(champion_code="x = 1", history=[])
    indexes = [q.index for q in qs]
    assert sorted(indexes) == list(range(len(qs)))


@pytest.mark.asyncio
async def test_llm_path_used_when_call_succeeds(monkeypatch):
    """When the LLM returns text, that text wins over the seed pool."""

    async def _ok(model, system, user, max_tokens=256, provider=None):
        # Embed the category so we can verify the prompt was scoped.
        for cat in CATEGORIES_USED:
            if f"Category: **{cat}**" in user:
                return f"LLM-authored idea for {cat}: do something concrete and meaningful."
        return "LLM-authored idea: fallback unscoped text long enough to pass the gate."

    monkeypatch.setattr(strategist, "complete_text", _ok)

    qs = await propose_questions(champion_code="x = 1", history=[])

    assert len(qs) == ACTIVE_PER_GEN
    for q in qs:
        assert q.text.startswith(f"LLM-authored idea for {q.category}")


def test_active_set_size_and_uniqueness():
    active = _select_active_categories(generation_number=1, champion_wins_per_category={})
    assert len(active) == ACTIVE_PER_GEN
    assert len(set(active)) == ACTIVE_PER_GEN
    assert set(active).issubset(set(CATEGORIES_USED))


def test_active_set_is_random(monkeypatch):
    """Selection goes through random.sample — verify by hijacking it."""
    captured: dict = {}

    def fake_sample(population, k):
        captured["population"] = list(population)
        captured["k"] = k
        return list(population[:k])

    monkeypatch.setattr(strategist.random, "sample", fake_sample)

    _select_active_categories(generation_number=1, champion_wins_per_category={})
    assert captured["k"] == ACTIVE_PER_GEN
    assert captured["population"] == list(CATEGORIES_USED)
