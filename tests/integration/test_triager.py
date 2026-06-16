"""Integration tests for agent.triager — US1 + US3 (research, propose, review, apply).

T008: test_research_issue — US1 research phase
T009: test_propose_action — US1 propose phase
T016: test_review_issue  — US3 CLI review gate
T017: test_apply_decision — US3 GitHub write actions
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.triager import (
    ReviewDecision,
    State,
    apply_decision,
    propose_action,
    research_issue,
    review_issue,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_ISSUE: dict[str, Any] = {
    "number": 42,
    "title": "Widget breaks on empty input",
    "url": "https://github.com/owner/repo/issues/42",
    "updated_at": "2024-01-01T00:00:00Z",
    "created_at": "2023-07-01T00:00:00Z",
    "author": "reporter1",
    "labels": ["bug", "stale"],
    "body": "When I submit an empty form the widget crashes.",
    "comments": [
        {"author": "maintainer", "createdAt": "2024-01-02T00:00:00Z", "body": "Can you reproduce?"},
    ],
}

SAMPLE_PROPOSAL: dict[str, Any] = {
    "close_issue": True,
    "close_issue_rationale": "No activity in 180 days and no response to maintainer question.",
    "add_labels": [],
    "add_labels_rationale": None,
    "remove_labels": [],
    "remove_labels_rationale": None,
    "assign_issue_to_copilot": False,
    "assign_issue_to_copilot_rationale": None,
    "post_comment": "Closing due to inactivity. Reopen if still reproducible with steps.",
    "rationale": "Issue is stale with no reporter response.",
}


def _mock_client() -> MagicMock:
    client = MagicMock()
    client.get_viewer_login = AsyncMock(return_value="maintainerbot")
    client.get_repository_labels = AsyncMock(return_value=[
        {"name": "bug", "description": "A bug", "color": "d73a4a"},
        {"name": "stale", "description": "Stale issue", "color": "cfd3d7"},
    ])
    return client


# ─────────────────────────────────────────────────────────────────────────────
# T008 — research_issue()
# ─────────────────────────────────────────────────────────────────────────────


class TestResearchIssue:
    async def test_sets_research_summary_on_state(self):
        state = State(issue=SAMPLE_ISSUE)
        with patch(
            "agent.triager.research_loop",
            new=AsyncMock(return_value="Research complete: issue appears stale."),
        ):
            await research_issue(state, active_issue_number=42)
        assert state.research_summary == "Research complete: issue appears stale."

    async def test_research_summary_is_non_empty_string(self):
        state = State(issue=SAMPLE_ISSUE)
        with patch(
            "agent.triager.research_loop",
            new=AsyncMock(return_value="Some summary."),
        ):
            await research_issue(state, active_issue_number=42)
        assert isinstance(state.research_summary, str)
        assert len(state.research_summary) > 0

    async def test_research_loop_called_with_system_and_tools(self):
        state = State(issue=SAMPLE_ISSUE)
        mock_loop = AsyncMock(return_value="summary")
        with patch("agent.triager.research_loop", new=mock_loop):
            await research_issue(state, active_issue_number=42)
        mock_loop.assert_called_once()
        call_kwargs = mock_loop.call_args
        # research_loop receives system_prompt, user_prompt, tools, [max_tool_calls]
        assert call_kwargs is not None

    async def test_raises_if_issue_not_set(self):
        state = State()
        with patch("agent.triager.research_loop", new=AsyncMock(return_value="x")):
            with pytest.raises((AssertionError, AttributeError, TypeError)):
                await research_issue(state, active_issue_number=42)


# ─────────────────────────────────────────────────────────────────────────────
# T009 — propose_action()
# ─────────────────────────────────────────────────────────────────────────────


class TestProposeAction:
    async def test_sets_proposal_on_state(self):
        state = State(issue=SAMPLE_ISSUE, research_summary="Issue is stale.")
        client = _mock_client()
        with patch("agent.triager.structured_output", return_value=SAMPLE_PROPOSAL):
            await propose_action(state, client)
        assert state.proposal is not None

    async def test_proposal_contains_required_fields(self):
        state = State(issue=SAMPLE_ISSUE, research_summary="Issue is stale.")
        client = _mock_client()
        with patch("agent.triager.structured_output", return_value=SAMPLE_PROPOSAL):
            await propose_action(state, client)
        proposal = state.proposal
        assert "close_issue" in proposal
        assert "rationale" in proposal
        assert "add_labels" in proposal
        assert "remove_labels" in proposal

    async def test_proposal_close_issue_matches_mock(self):
        state = State(issue=SAMPLE_ISSUE, research_summary="Stale.")
        client = _mock_client()
        with patch("agent.triager.structured_output", return_value=SAMPLE_PROPOSAL):
            await propose_action(state, client)
        assert state.proposal["close_issue"] is True

    async def test_structured_output_called_with_proposal_model(self):
        from agent.triager import ProposalModel

        state = State(issue=SAMPLE_ISSUE, research_summary="Stale.")
        client = _mock_client()
        with patch("agent.triager.structured_output", return_value=SAMPLE_PROPOSAL) as mock_so:
            await propose_action(state, client)
        mock_so.assert_called_once()
        _, schema_arg = mock_so.call_args[0]
        assert schema_arg is ProposalModel

    async def test_viewer_login_used_for_prompt(self):
        state = State(issue=SAMPLE_ISSUE, research_summary="Stale.")
        client = _mock_client()
        prompts_seen: list[str] = []

        def capture(prompt: str, schema: type) -> dict:
            prompts_seen.append(prompt)
            return SAMPLE_PROPOSAL

        with patch("agent.triager.structured_output", side_effect=capture):
            await propose_action(state, client)

        assert len(prompts_seen) == 1
        assert "maintainerbot" in prompts_seen[0]

    async def test_raises_if_research_summary_not_set(self):
        state = State(issue=SAMPLE_ISSUE)
        client = _mock_client()
        with patch("agent.triager.structured_output", return_value=SAMPLE_PROPOSAL):
            with pytest.raises((AssertionError, AttributeError, TypeError)):
                await propose_action(state, client)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for US3 tests
# ─────────────────────────────────────────────────────────────────────────────


def _apply_client() -> MagicMock:
    """Mock client with AsyncMock write methods for apply_decision tests."""
    client = MagicMock()
    client.close_issue = AsyncMock()
    client.post_comment = AsyncMock()
    client.add_label = AsyncMock()
    client.remove_label = AsyncMock()
    client.assign_issue_to_copilot = AsyncMock()
    return client


def _sample_decision(**overrides) -> ReviewDecision:
    defaults = dict(
        approved=True,
        issue_number=42,
        close_issue=True,
        add_labels=[],
        remove_labels=[],
        assign_issue_to_copilot=False,
        post_comment="Closing due to inactivity.",
        note=None,
    )
    defaults.update(overrides)
    return ReviewDecision(**defaults)


# ─────────────────────────────────────────────────────────────────────────────
# T016 — review_issue()
# ─────────────────────────────────────────────────────────────────────────────


class TestReviewIssue:
    async def test_accept_returns_approved_true(self):
        state = State(issue=SAMPLE_ISSUE, proposal=SAMPLE_PROPOSAL)
        with patch("builtins.input", return_value="a"):
            decision = review_issue(state)
        assert decision.approved is True

    async def test_skip_returns_approved_false(self):
        state = State(issue=SAMPLE_ISSUE, proposal=SAMPLE_PROPOSAL)
        with patch("builtins.input", return_value="s"):
            decision = review_issue(state)
        assert decision.approved is False

    async def test_quit_raises_system_exit(self):
        state = State(issue=SAMPLE_ISSUE, proposal=SAMPLE_PROPOSAL)
        with patch("builtins.input", return_value="q"):
            with pytest.raises(SystemExit):
                review_issue(state)

    async def test_edit_blank_inputs_keep_original_values(self):
        state = State(issue=SAMPLE_ISSUE, proposal=SAMPLE_PROPOSAL)
        # "e" selects edit, then 5 blank inputs keep all original values
        with patch("builtins.input", side_effect=["e", "", "", "", "", ""]):
            decision = review_issue(state)
        assert decision.approved is True
        assert decision.close_issue == SAMPLE_PROPOSAL["close_issue"]
        assert decision.add_labels == SAMPLE_PROPOSAL["add_labels"]
        assert decision.remove_labels == SAMPLE_PROPOSAL["remove_labels"]
        assert decision.assign_issue_to_copilot == SAMPLE_PROPOSAL["assign_issue_to_copilot"]
        assert decision.post_comment == SAMPLE_PROPOSAL["post_comment"]


# ─────────────────────────────────────────────────────────────────────────────
# T017 — apply_decision()
# ─────────────────────────────────────────────────────────────────────────────


class TestApplyDecision:
    async def test_approved_close_and_comment_calls_both(self):
        decision = _sample_decision(approved=True, close_issue=True, post_comment="Closing.")
        client = _apply_client()
        await apply_decision(decision, client)
        client.close_issue.assert_called_once()
        client.post_comment.assert_called_once()

    async def test_approved_no_close_skips_close(self):
        decision = _sample_decision(approved=True, close_issue=False, post_comment=None)
        client = _apply_client()
        await apply_decision(decision, client)
        client.close_issue.assert_not_called()

    async def test_not_approved_no_write_methods_called(self):
        decision = _sample_decision(approved=False)
        client = _apply_client()
        await apply_decision(decision, client)
        client.close_issue.assert_not_called()
        client.post_comment.assert_not_called()
        client.add_label.assert_not_called()
        client.remove_label.assert_not_called()
        client.assign_issue_to_copilot.assert_not_called()
