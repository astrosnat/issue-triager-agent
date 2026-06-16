# Research: Claude Max/Pro Backend

**Phase 0 output for**: specs/001-claude-max-backend/plan.md

---

## 1. Claude Code CLI Subprocess Interface

**Decision**: Use `claude --print <prompt>` as a blocking subprocess call from Python.

**Rationale**:
- `claude` CLI is already installed on any machine running Claude Code
- `--print` flag produces a single response and exits (non-interactive)
- No API key needed — uses the authenticated subscription session
- Exit code 0 on success; non-zero on auth failure or model error

**Call pattern**:
```python
import subprocess, sys

def call_claude(prompt: str, *, model: str | None = None) -> str:
    cmd = ["claude", "--print"]
    if model:
        cmd += ["--model", model]
    cmd.append(prompt)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"claude CLI error (exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()
```

**Auth error detection**: If `CLAUDE_CODE_AUTH` or subscription is expired, the CLI
prints to stderr and exits 1. The wrapper surfaces this as a `RuntimeError` with a
message that tells the user to re-authenticate (`claude auth login`).

**Alternatives considered**:
- `langchain_anthropic` + `ANTHROPIC_API_KEY` — requires paid API access (rejected: user constraint)
- `anthropic` SDK directly — same constraint
- OpenAI-compatible Claude proxy — none available without API key

---

## 2. Tool Calling via Subprocess

**Decision**: Implement a manual ReAct loop. Each iteration sends the full conversation
history (system prompt + prior turns + last tool result) to `claude --print`. Parse
Claude's response for JSON tool call blocks. Execute the tool. Feed the result back.

**Rationale**:
- `claude --print` does not accept tool schemas as CLI arguments
- Claude naturally outputs structured JSON when asked in the system prompt
- The existing codebase already limits research to 4 tool calls (`ToolCallLimitMiddleware`)
- A manual loop matches the existing logic precisely

**Tool call protocol** (prompt-level):

System prompt section instructs Claude to respond with a JSON object in one of two
shapes:

```json
// Shape A — Claude wants to call a tool
{
  "type": "tool_call",
  "tool": "search_issues",
  "args": { "query": "..." }
}

// Shape B — Claude is done with research
{
  "type": "final_answer",
  "content": "... research summary ..."
}
```

After each Shape A response, execute the tool and prepend the result as a
`<tool_result>` block in the next turn. After Shape B (or when tool call limit is
reached), the `content` field is the `research_summary`.

**Parser**: `json.loads()` after stripping markdown fences if present. If parsing
fails, treat the entire response as a final answer (graceful degradation).

**Alternatives considered**:
- MCP server for GitHub tools exposed to Claude Code — correct long-term approach but
  over-scoped for this change; consider as future enhancement
- Single-shot prompt with all context pre-loaded — loses follow-up search capability
  (rejected: would degrade proposal quality)

---

## 3. Structured Output (Proposal Generation)

**Decision**: Ask Claude to output the proposal as a JSON block matching `ProposalModel`
schema. Parse with `json.loads()` + `ProposalModel.model_validate()`.

**Rationale**:
- Simple and reliable; no streaming required
- Schema is already defined as a Pydantic model — reuse as-is
- Claude reliably outputs valid JSON when the schema is embedded in the prompt

**Prompt pattern** (added to propose_action_prompt.md.jinja2 header):

```
Respond ONLY with a valid JSON object. No markdown, no explanation, no code fences.
Schema:
{{ schema_json }}
```

Where `schema_json = ProposalModel.model_json_schema()` serialized as compact JSON.

**Error handling**: If JSON parse fails, retry once with an explicit correction message
(prepend "Your previous response was not valid JSON. Try again."). Raise `RuntimeError`
after two failures.

**Alternatives considered**:
- Asking Claude to fill a template — prone to formatting errors in non-JSON fields
- Pydantic `model_validate_json` directly — same approach, just calling it by its name

---

## 4. Human Review Gate (CLI-based)

**Decision**: Print the proposal to stdout (rendered via the existing
`review_template.md.jinja2`), then use `input()` to read an `a/e/s/q` choice.

**Review prompt format**:

```
═══════════════════════════════════════════════
 TRIAGE PROPOSAL — Issue #1234
═══════════════════════════════════════════════
[rendered review_template output]

 [a]ccept  [e]dit  [s]kip  [q]uit
 > 
```

**Edit flow**: If user types `e`, prompt for each field individually. Fields that the
user leaves blank keep the original value.

**Rationale**:
- Satisfies Principle I (no GitHub write without human approval)
- Zero new dependencies
- Works in any terminal including the VS Code integrated terminal and Claude Code CLI

**Alternatives considered**:
- Web UI (e.g., simple Flask page) — over-scoped; adds a dependency and a server process
- TUI library (e.g., `rich`) — nice-to-have; can be added later without changing the
  interface contract

---

## 5. Dependency Changes

| Package | Action | Reason |
|---------|--------|--------|
| `langgraph` | REMOVE | Replaced by plain Python orchestration in `triager.py` |
| `langgraph-sdk` | REMOVE | Agent Inbox integration no longer needed |
| `langchain` | REMOVE | No longer used |
| `langchain-openai` | REMOVE | No longer used |
| `azure-identity` | REMOVE | No Azure credentials needed |
| `httpx` | KEEP | GitHub API calls in `github_client.py` |
| `jinja2` | KEEP | Prompt template rendering |
| `pydantic` | KEEP | ProposalModel, data validation |
| `python-dotenv` | KEEP | `.env` loading |

Dev dependencies unchanged: `mypy`, `ruff`, `pytest`.

LangGraph dev server removed — entry point becomes `uv run python src/agent/main.py`.

---

## 6. Test Surface

Per Principle III (Test-First Development), tests MUST be written before implementation.

| Module | Test type | What to test |
|--------|-----------|--------------|
| `claude_backend.py` | Unit (mock subprocess) | Correct prompt construction; JSON parsing; auth error surfacing; retry logic |
| `triager.py` | Integration (mock GitHubClient + mock claude) | Full select→research→propose→review→apply flow; skip and edit paths |
| `github_client.py` | Existing — no new tests needed unless behaviour changes |

**Test strategy**: Mock `subprocess.run` to return canned `claude` CLI responses.
Mock `GitHubClient` to return fixture issue data. No live network calls in unit tests.

---

## 7. Environment Variables (after change)

| Variable | Required | Notes |
|----------|----------|-------|
| `GITHUB_TOKEN` | YES | GitHub API access (unchanged) |
| `TARGET_REPO` | NO | Defaults to `Azure-samples/azure-search-openai-demo` |
| ~~`API_HOST`~~ | REMOVED | No longer used |
| ~~`AZURE_OPENAI_ENDPOINT`~~ | REMOVED | |
| ~~`AZURE_OPENAI_CHAT_DEPLOYMENT`~~ | REMOVED | |
| ~~`AZURE_OPENAI_VERSION`~~ | REMOVED | |
| ~~`AZURE_OPENAI_API_KEY`~~ | REMOVED | |
| ~~`AZURE_TENANT_ID`~~ | REMOVED | |
| ~~`GITHUB_MODEL`~~ | REMOVED | |
| ~~`LANGSMITH_*`~~ | REMOVED | |
