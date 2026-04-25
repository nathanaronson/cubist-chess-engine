"""Tests for darwin.agents.adversary.

The LLM call is mocked. Empty Critique on any failure is a load-bearing
contract (the orchestrator skips the fixer when ``crit.full`` is
empty), so it gets dedicated coverage. Also covers the SUMMARY/full
parser including tolerant fallbacks.
"""

from __future__ import annotations

import pytest

from darwin.agents import adversary
from darwin.agents.adversary import Critique, _parse_response, critique_engine
from darwin.agents.strategist import Question


@pytest.fixture
def question() -> Question:
    return Question(
        index=0,
        category="quiescence",
        text="Add capture-only quiescence search to depth 4.",
    )


@pytest.mark.asyncio
async def test_returns_critique_on_success(monkeypatch, question):
    captured: dict = {}

    async def fake_complete_text(model, system, user, max_tokens=256, provider=None):
        captured["model"] = model
        captured["provider"] = provider
        captured["user"] = user
        return (
            "SUMMARY: Quiescence has no depth bound and will forfeit on time.\n"
            "\n"
            "Quiescence has no depth bound — at high capture density this "
            "will exceed the 5s budget and forfeit on time. Cap the recursion "
            "at depth 4. The eval also has a sign error in the negamax return."
        )

    monkeypatch.setattr(adversary, "complete_text", fake_complete_text)

    crit = await critique_engine(question, "code goes here", "gen1-quiescence-abc123")

    assert isinstance(crit, Critique)
    assert crit.summary.startswith("Quiescence has no depth bound")
    assert "5s budget" in crit.full
    assert "SUMMARY:" not in crit.full
    assert "capture-only quiescence" in captured["user"]
    assert "code goes here" in captured["user"]


@pytest.mark.asyncio
async def test_returns_empty_critique_on_llm_failure(monkeypatch, question):
    async def boom(*args, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(adversary, "complete_text", boom)

    crit = await critique_engine(question, "code", "gen1-quiescence-abc123")
    assert crit.summary == ""
    assert crit.full == ""


@pytest.mark.asyncio
async def test_returns_empty_critique_on_short_response(monkeypatch, question):
    async def fake(*args, **kwargs):
        return "ok"

    monkeypatch.setattr(adversary, "complete_text", fake)

    crit = await critique_engine(question, "code", "gen1-quiescence-abc123")
    assert crit.summary == ""
    assert crit.full == ""


@pytest.mark.asyncio
async def test_uses_adversary_provider_override(monkeypatch, question):
    """Provider routing for adversary must come from settings.adversary_provider."""
    from darwin.config import settings

    monkeypatch.setattr(settings, "adversary_provider", "gemini")

    captured: dict = {}

    async def fake(model, system, user, max_tokens=256, provider=None):
        captured["provider"] = provider
        return (
            "SUMMARY: Looks solid.\n\n"
            "A long enough critique to clear the 20-char minimum threshold easily."
        )

    monkeypatch.setattr(adversary, "complete_text", fake)

    await critique_engine(question, "code", "gen1-quiescence-abc123")
    assert captured["provider"] == "gemini"


def test_parse_response_extracts_summary_and_full():
    crit = _parse_response(
        "SUMMARY: One-line verdict here.\n"
        "\n"
        "First sentence of body. Second sentence. Third sentence."
    )
    assert crit.summary == "One-line verdict here."
    assert crit.full.startswith("First sentence")
    assert "SUMMARY:" not in crit.full


def test_parse_response_tolerates_lowercase_prefix():
    crit = _parse_response("Summary: low-case ok.\n\nbody body body body body.")
    assert crit.summary == "low-case ok."
    assert "body body body" in crit.full


def test_parse_response_tolerates_missing_blank_line():
    crit = _parse_response("SUMMARY: tight.\nbody body body body body body.")
    assert crit.summary == "tight."
    assert crit.full.startswith("body body body")


def test_parse_response_falls_back_when_summary_prefix_missing():
    """When the model omits the SUMMARY: prefix, derive a one-sentence
    summary from the start of the body so the dashboard still renders
    something meaningful."""
    crit = _parse_response(
        "Quiescence search has no bound. The eval has a sign error too."
    )
    assert crit.summary.startswith("Quiescence search has no bound")
    assert crit.full.startswith("Quiescence search has no bound")


def test_parse_response_empty_returns_empty_critique():
    crit = _parse_response("")
    assert crit.summary == ""
    assert crit.full == ""
