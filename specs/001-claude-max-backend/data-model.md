# Data Model: Claude Max/Pro Backend

**Phase 1 output for**: specs/001-claude-max-backend/plan.md

---

## Core Data Structures

### State (unchanged)

```python
@dataclass
class State:
    issue: dict[str, Any] | None = None          # Selected issue details
    proposal: dict[str, Any] | None = None        # Structured triage proposal
    decision: dict[str, Any] | None = None        # Human review decision
    review_note: str | None = None                # Optional reviewer note
    research_summary: str | None = None           # Research phase output
```

No changes to State — the orchestrator in `triager.py` passes this dataclass
through each phase the same way LangGraph nodes did.

---

### ProposalModel (unchanged)

```python
class ProposalModel(BaseModel):
    close_issue: bool
    close_issue_rationale: str | None
    add_labels: list[str]
    add_labels_rationale: str | None
    remove_labels: list[str]
    remove_labels_rationale: str | None
    assign_issue_to_copilot: bool
    assign_issue_to_copilot_rationale: str | None
    post_comment: str | None
    rationale: str
```

The Pydantic model is reused as-is. Its `model_json_schema()` is embedded in the
proposal prompt so Claude knows the exact output format expected.

---

### ToolCall (new — internal to claude_backend.py)

```python
@dataclass
class ToolCall:
    tool: str           # Tool name, e.g. "search_issues"
    args: dict[str, Any]

@dataclass
class ClaudeResponse:
    type: Literal["tool_call", "final_answer"]
    tool_call: ToolCall | None        # present when type == "tool_call"
    content: str | None               # present when type == "final_answer"
```

Used internally by the ReAct loop in `claude_backend.py`. Not exposed to callers.

---

### ReviewDecision (new — returned from CLI review step)

```python
@dataclass
class ReviewDecision:
    approved: bool
    close_issue: bool
    add_labels: list[str]
    remove_labels: list[str]
    assign_issue_to_copilot: bool
    post_comment: str | None
    note: str | None               # free-text from "respond" or "skip" paths
```

Mirrors the existing `decision` dict in the LangGraph version. Typed for clarity.

---

## Module Responsibilities

| Module | Owns | Does NOT own |
|--------|------|--------------|
| `github_client.py` | GitHub API I/O | LLM, review, orchestration |
| `claude_backend.py` | subprocess calls to `claude`; tool-call loop; JSON parsing | GitHub tools (passed in as callables) |
| `triager.py` | Orchestration (select → research → propose → review → apply); State threading | LLM calls, GitHub API details |
| `main.py` | Entry point; env loading; error surfacing | Business logic |

---

## Tool Registry (unchanged names, new binding)

The same seven GitHub tools are available to the research agent. They are defined in
`triager.py` as async functions and passed to `claude_backend.py` as a dict:

```python
TOOLS: dict[str, Callable] = {
    "search_issues": tool_search_issues,
    "search_code": tool_search_code,
    "search_pull_requests": tool_search_pull_requests,
    "get_pull_request": tool_get_pull_request,
    "fetch_file": tool_fetch_file,
    "get_issue": tool_get_issue,
    "list_repository_files": tool_list_repository_files,
}
```

`claude_backend.py` receives only the dict — it does not import from `github_client.py`
directly. This keeps the boundary clean for testing (tools can be mocked independently).

---

## State Transitions

```
main.py
  └─► triager.run()
        ├─► select_stale_issue()   → State.issue
        ├─► research_issue()       → State.research_summary
        │     └─► claude_backend.research_loop(tools, prompt) → str
        ├─► propose_action()       → State.proposal
        │     └─► claude_backend.structured_output(prompt, ProposalModel) → dict
        ├─► review_issue()         → State.decision
        │     └─► cli_review(proposal) → ReviewDecision
        └─► apply_decision()       → (GitHub side effects)
              └─► github_client.*
```
