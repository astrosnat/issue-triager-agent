"""Claude Code CLI subprocess wrapper for LLM calls.

Provides three public functions:
- call_claude: one-shot subprocess call, returns text response
- research_loop: multi-turn tool-calling loop using the claude CLI
- structured_output: single call with JSON schema enforcement and retry
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """A tool invocation parsed from a claude CLI response."""

    tool: str
    args: dict[str, Any]


@dataclass
class ClaudeResponse:
    """Parsed claude CLI response — either a tool call or a final answer."""

    type: str  # "tool_call" or "final_answer"
    tool_call: ToolCall | None = None
    content: str | None = None


def call_claude(prompt: str, *, timeout: int = 120) -> str:
    """Invoke the claude CLI with --print and return the stripped response.

    Args:
        prompt: The prompt to send to Claude.
        timeout: Seconds before the subprocess is killed.

    Returns:
        Stripped stdout text from the claude CLI.

    Raises:
        FileNotFoundError: If the claude binary is not on PATH.
        RuntimeError: On non-zero exit code or subprocess timeout.
    """
    cmd = ["claude", "--print", prompt]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"claude CLI timed out after {timeout}s")
    # FileNotFoundError propagates to caller as-is

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "not authenticated" in stderr.lower() or "unauthenticated" in stderr.lower():
            raise RuntimeError(
                f"Claude CLI not authenticated (exit {result.returncode}). "
                "Run: claude auth login"
            )
        raise RuntimeError(
            f"claude CLI error (exit {result.returncode}): {stderr}"
        )

    return result.stdout.strip()


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from a response string."""
    stripped = text.strip()
    match = re.match(r"```(?:json)?\s*\n(.*?)\n```", stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def _parse_response(text: str) -> ClaudeResponse:
    """Parse a claude CLI response into a ClaudeResponse.

    Returns a tool_call response if the text is valid JSON with type=="tool_call",
    a final_answer if type=="final_answer", or treats raw text as a final answer.
    """
    cleaned = _strip_fences(text)
    try:
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            return ClaudeResponse(type="final_answer", content=text)

        if data.get("type") == "tool_call":
            return ClaudeResponse(
                type="tool_call",
                tool_call=ToolCall(
                    tool=data.get("tool", ""),
                    args=data.get("args") or {},
                ),
            )
        if data.get("type") == "final_answer":
            return ClaudeResponse(
                type="final_answer",
                content=data.get("content", text),
            )
        return ClaudeResponse(type="final_answer", content=text)
    except json.JSONDecodeError:
        return ClaudeResponse(type="final_answer", content=text)


async def research_loop(
    system_prompt: str,
    user_prompt: str,
    tools: dict[str, Callable],
    max_tool_calls: int = 4,
) -> str:
    """Run a multi-turn research loop via the claude CLI.

    Dispatches tool calls until a final_answer is produced or max_tool_calls
    is reached, at which point a forced summary call is made.

    Args:
        system_prompt: Instructions and tool descriptions for Claude.
        user_prompt: The initial research question / issue context.
        tools: Mapping of tool name → async callable.
        max_tool_calls: Maximum tool invocations before forcing a summary.

    Returns:
        Research summary string.
    """
    conversation = f"{system_prompt}\n\n---\n\n{user_prompt}"
    tool_call_count = 0

    while True:
        response_text = call_claude(conversation)
        parsed = _parse_response(response_text)

        if parsed.type == "final_answer":
            return parsed.content or response_text

        if parsed.tool_call is None:
            return response_text

        tc = parsed.tool_call
        tool_call_count += 1

        if tc.tool in tools:
            try:
                tool_result = await tools[tc.tool](**tc.args)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Tool '%s' raised: %s", tc.tool, exc)
                tool_result = json.dumps({"error": str(exc)})
        else:
            logger.warning("Unknown tool '%s'; skipping", tc.tool)
            tool_result = json.dumps({"error": f"Tool '{tc.tool}' not available"})

        conversation = (
            f"{conversation}\n\n"
            f"[Tool: {tc.tool}({json.dumps(tc.args)})]\n"
            f"Result: {tool_result}"
        )

        if tool_call_count >= max_tool_calls:
            conversation = (
                f"{conversation}\n\n"
                "No more tool calls allowed. Summarize your findings now."
            )
            final_text = call_claude(conversation)
            final = _parse_response(final_text)
            return final.content or final_text


def structured_output(prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
    """Call claude and parse the response as a validated Pydantic model dict.

    Embeds the JSON schema in the prompt. Retries once on parse failure.

    Args:
        prompt: The user-facing content portion of the prompt.
        schema: Pydantic model class whose schema Claude must match.

    Returns:
        dict produced by schema.model_dump() on the validated response.

    Raises:
        RuntimeError: If two consecutive calls produce unparseable JSON.
    """
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    base_instruction = (
        "Respond ONLY with a valid JSON object. "
        "No markdown, no explanation, no code fences.\n"
        f"Schema:\n{schema_json}\n\n"
    )

    last_response = ""
    for attempt in range(2):
        if attempt == 0:
            full_prompt = base_instruction + prompt
        else:
            full_prompt = (
                "Your previous response was not valid JSON. "
                "Respond ONLY with a valid JSON object matching the schema.\n"
                f"Schema:\n{schema_json}\n\n"
                + prompt
            )

        last_response = call_claude(full_prompt)
        cleaned = _strip_fences(last_response)

        try:
            data = json.loads(cleaned)
            validated = schema.model_validate(data)
            return validated.model_dump()
        except Exception:  # noqa: BLE001
            logger.warning("structured_output attempt %d failed", attempt + 1)

    raise RuntimeError(
        f"Claude structured output failed after 2 attempts. "
        f"Last response: {last_response[:200]!r}"
    )
