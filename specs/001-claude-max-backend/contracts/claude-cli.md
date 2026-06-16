# Contract: Claude CLI Subprocess Interface

**Used by**: `src/agent/claude_backend.py`

---

## Invocation

```
claude --print [--model <model-id>] "<prompt>"
```

| Field | Value |
|-------|-------|
| Exit 0 | Success — stdout contains the response text |
| Exit non-0 | Failure — stderr contains the error message |
| Auth error | Exit non-0, stderr matches `"not authenticated"` or similar |
| Timeout | Handled by `subprocess.run(timeout=120)` → raises `TimeoutExpired` |

---

## Research Loop Protocol

### System prompt contract (embedded in research_prompt.md.jinja2)

The system prompt MUST include the following instruction block:

```
## Response Format

You MUST respond with a single JSON object (no markdown fences, no explanation).
Use one of these two shapes:

Shape A — call a tool:
{
  "type": "tool_call",
  "tool": "<tool_name>",
  "args": { ... }
}

Shape B — research complete:
{
  "type": "final_answer",
  "content": "<research summary text>"
}

Available tools:
<tool_name>: <description>
...
```

### Turn structure passed to each `claude --print` call

```
[System prompt with tool descriptions]

---

[Turn 1] User: <initial research question + issue details>
[Turn 1] Assistant: <Claude response — tool_call or final_answer>
[Tool result] <tool_name>(<args>) → <result JSON>
[Turn 2] User: Continue.
[Turn 2] Assistant: ...
...
```

The full history is concatenated as a single string on each subprocess call.

### Termination conditions

1. Claude returns `{ "type": "final_answer", ... }`
2. Tool call count reaches limit (currently 4 — matching existing `ToolCallLimitMiddleware`)
3. JSON parse fails twice in a row → raise `RuntimeError`

---

## Structured Output Protocol

### Prompt contract (prepended to propose_action_prompt.md.jinja2 output)

```
Respond ONLY with a valid JSON object that matches this schema exactly.
No markdown fences, no explanation, no extra fields.

Schema:
<ProposalModel.model_json_schema() as compact JSON>
```

### Success condition

`json.loads(response)` succeeds AND `ProposalModel.model_validate(parsed)` succeeds.

### Failure handling

1. First failure: retry with prepended correction:
   `"Your previous response was not valid JSON. Respond ONLY with the JSON object."`
2. Second failure: raise `RuntimeError("Claude structured output failed after 2 attempts")`

---

## Error Surfacing Contract

| Error condition | Exception raised | Message pattern |
|----------------|-----------------|-----------------|
| `claude` not on PATH | `FileNotFoundError` | propagated as-is |
| Auth expired/missing | `RuntimeError` | `"Claude CLI not authenticated. Run: claude auth login"` |
| Model error (non-auth) | `RuntimeError` | `"claude CLI error (exit N): <stderr>"` |
| Subprocess timeout | `RuntimeError` | `"claude CLI timed out after 120s"` |
| JSON parse failure (×2) | `RuntimeError` | `"Claude structured output failed after 2 attempts"` |

All errors propagate to `triager.py` which logs them and surfaces to the user via
`main.py` with a user-friendly message (never a raw traceback on stdout).
