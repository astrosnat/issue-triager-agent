"""Unit tests for agent.claude_backend.

Written before claude_backend.py exists (TDD red phase).
Run T007 to implement the module and make these pass.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from agent.claude_backend import call_claude, research_loop, structured_output


# Minimal model for structured_output tests
class _Sample(BaseModel):
    name: str
    count: int


# Canned JSON responses for research_loop tests
_TOOL_CALL = json.dumps(
    {"type": "tool_call", "tool": "search_issues", "args": {"query": "stale"}},
)
_FINAL_ANSWER = json.dumps(
    {"type": "final_answer", "content": "Research complete: issue is stale."},
)
_SAMPLE_JSON = json.dumps({"name": "test", "count": 42})
_BAD_JSON = "not json { at all }"


# ─────────────────────────────────────────────────────────────────────────────
# T004 — call_claude()
# ─────────────────────────────────────────────────────────────────────────────


def _proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


class TestCallClaude:
    def test_success_returns_stripped_stdout(self):
        with patch("subprocess.run", return_value=_proc(0, stdout="  response\n")):
            assert call_claude("prompt") == "response"

    def test_subprocess_command_includes_print_flag_and_prompt(self):
        with patch("subprocess.run", return_value=_proc(0, stdout="ok")) as mock_run:
            call_claude("my prompt")
        cmd: list[str] = mock_run.call_args[0][0]
        assert "claude" in cmd
        assert "--print" in cmd
        assert "my prompt" in cmd

    def test_nonzero_exit_raises_runtime_error(self):
        with patch("subprocess.run", return_value=_proc(1, stderr="error")):
            with pytest.raises(RuntimeError):
                call_claude("prompt")

    def test_nonzero_exit_message_contains_exit_code(self):
        with patch("subprocess.run", return_value=_proc(2, stderr="crash")):
            with pytest.raises(RuntimeError, match="2"):
                call_claude("prompt")

    def test_auth_error_message_suggests_reauth(self):
        with patch("subprocess.run", return_value=_proc(1, stderr="not authenticated")):
            with pytest.raises(RuntimeError) as exc_info:
                call_claude("prompt")
        msg = str(exc_info.value).lower()
        assert "auth" in msg or "login" in msg or "authenticated" in msg

    def test_timeout_raises_runtime_error_with_timed_out(self):
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=120),
        ):
            with pytest.raises(RuntimeError, match="timed out"):
                call_claude("prompt")

    def test_binary_not_found_propagates_as_file_not_found_error(self):
        with patch("subprocess.run", side_effect=FileNotFoundError("claude")):
            with pytest.raises(FileNotFoundError):
                call_claude("prompt")


# ─────────────────────────────────────────────────────────────────────────────
# T005 — research_loop()
# ─────────────────────────────────────────────────────────────────────────────


class TestResearchLoop:
    async def test_immediate_final_answer_no_tool_calls(self):
        tool = AsyncMock(return_value="{}")
        with patch("agent.claude_backend.call_claude", return_value=_FINAL_ANSWER):
            result = await research_loop("sys", "user", {"search_issues": tool})
        assert result == "Research complete: issue is stale."
        tool.assert_not_called()

    async def test_tool_called_once_then_final_answer(self):
        tool = AsyncMock(return_value='{"items": ["issue1"]}')
        with patch(
            "agent.claude_backend.call_claude",
            side_effect=[_TOOL_CALL, _FINAL_ANSWER],
        ):
            result = await research_loop("sys", "user", {"search_issues": tool})
        assert result == "Research complete: issue is stale."
        tool.assert_called_once_with(query="stale")

    async def test_tool_result_passed_to_next_call(self):
        tool = AsyncMock(return_value='{"hits": 3}')
        prompts_seen: list[str] = []

        def capture_call(prompt: str, **kwargs: Any) -> str:
            prompts_seen.append(prompt)
            return _FINAL_ANSWER if len(prompts_seen) > 1 else _TOOL_CALL

        with patch("agent.claude_backend.call_claude", side_effect=capture_call):
            await research_loop("sys", "user", {"search_issues": tool})

        # Second call should include the tool result somewhere in the prompt
        assert len(prompts_seen) == 2
        assert "hits" in prompts_seen[1] or '{"hits": 3}' in prompts_seen[1]

    async def test_max_tool_calls_terminates_loop(self):
        tool = AsyncMock(return_value="{}")
        # Always return a tool_call; loop must stop on its own
        forced_summary = json.dumps({"type": "final_answer", "content": "forced"})
        # Provide enough side_effects: N tool_calls + 1 summary (from forced final call)
        side_effects = [_TOOL_CALL, _TOOL_CALL, forced_summary]
        with patch("agent.claude_backend.call_claude", side_effect=side_effects):
            result = await research_loop("sys", "user", {"search_issues": tool}, max_tool_calls=2)
        assert isinstance(result, str)
        assert len(result) > 0
        assert tool.call_count == 2

    async def test_invalid_json_response_treated_as_final_answer(self):
        tool = AsyncMock()
        with patch("agent.claude_backend.call_claude", return_value="plain text"):
            result = await research_loop("sys", "user", {"search_issues": tool})
        assert result == "plain text"
        tool.assert_not_called()

    async def test_unknown_tool_skipped_loop_continues(self):
        unknown_call = json.dumps(
            {"type": "tool_call", "tool": "nonexistent", "args": {}},
        )
        with patch(
            "agent.claude_backend.call_claude",
            side_effect=[unknown_call, _FINAL_ANSWER],
        ):
            result = await research_loop("sys", "user", {})
        assert result == "Research complete: issue is stale."


# ─────────────────────────────────────────────────────────────────────────────
# T006 — structured_output()
# ─────────────────────────────────────────────────────────────────────────────


class TestStructuredOutput:
    def test_valid_json_returns_validated_dict(self):
        with patch("agent.claude_backend.call_claude", return_value=_SAMPLE_JSON):
            result = structured_output("prompt", _Sample)
        assert result["name"] == "test"
        assert result["count"] == 42

    def test_json_in_markdown_fence_is_parsed(self):
        fenced = f"```json\n{_SAMPLE_JSON}\n```"
        with patch("agent.claude_backend.call_claude", return_value=fenced):
            result = structured_output("prompt", _Sample)
        assert result["name"] == "test"

    def test_schema_fields_appear_in_prompt(self):
        with patch(
            "agent.claude_backend.call_claude", return_value=_SAMPLE_JSON
        ) as mock_call:
            structured_output("base prompt", _Sample)
        prompt_used: str = mock_call.call_args[0][0]
        assert "name" in prompt_used
        assert "count" in prompt_used

    def test_invalid_then_valid_retries_once(self):
        with patch(
            "agent.claude_backend.call_claude",
            side_effect=[_BAD_JSON, _SAMPLE_JSON],
        ) as mock_call:
            result = structured_output("prompt", _Sample)
        assert result["name"] == "test"
        assert mock_call.call_count == 2

    def test_retry_prompt_mentions_json(self):
        prompts: list[str] = []

        def capture(prompt: str, **_: Any) -> str:
            prompts.append(prompt)
            return _SAMPLE_JSON if len(prompts) > 1 else _BAD_JSON

        with patch("agent.claude_backend.call_claude", side_effect=capture):
            structured_output("base", _Sample)

        assert len(prompts) == 2
        assert "json" in prompts[1].lower() or "JSON" in prompts[1]

    def test_double_invalid_raises_runtime_error(self):
        with patch("agent.claude_backend.call_claude", return_value=_BAD_JSON):
            with pytest.raises(RuntimeError, match="structured output failed"):
                structured_output("prompt", _Sample)
