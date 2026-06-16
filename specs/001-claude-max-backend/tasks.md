---

description: "Task list template for feature implementation"
---

# Tasks: Claude Max/Pro Backend

**Input**: Design documents from `/specs/001-claude-max-backend/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/claude-cli.md ✅

**Tests**: Included — required by constitution Principle III (Test-First Development).

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1=P1, US2=P2, US3=P3)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Remove old dependencies and scaffold new directory structure.

- [x] T001 Remove `azure-identity`, `langchain`, `langchain-openai`, `langgraph`, `langgraph-sdk` from `[project].dependencies` in `pyproject.toml`; remove `langgraph-cli[inmem]` from `[dependency-groups].dev`
- [x] T002 Delete `langgraph.json` (LangGraph dev server config, no longer needed)
- [x] T003 [P] Create `tests/unit/__init__.py` and `tests/integration/__init__.py` (empty files)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement and test `claude_backend.py` — the core subprocess wrapper that all LLM calls go through. Nothing else can work until this exists and passes tests.

**⚠️ CRITICAL**: Write tests first (red), then implement (green). No user story work until this phase is complete.

### Tests for claude_backend.py

> **NOTE: Write these tests FIRST, ensure they FAIL before implementing `claude_backend.py`**

- [ ] T004 [P] Write failing unit tests for `call_claude()` in `tests/unit/test_claude_backend.py`:
  test successful response (mock `subprocess.run` returning exit 0 + stdout text);
  test auth error (exit 1 + stderr "not authenticated" → RuntimeError with re-auth message);
  test timeout (`TimeoutExpired` → RuntimeError);
  test binary not found (`FileNotFoundError` propagated)
- [ ] T005 [P] Write failing unit tests for `research_loop()` in `tests/unit/test_claude_backend.py`:
  test tool_call parse and dispatch (mock returns Shape A JSON → tool called → next call receives result);
  test final_answer parse (mock returns Shape B JSON → loop exits, content returned);
  test max-tool-calls limit (mock always returns tool_call → loop stops at 4 calls, forces final answer);
  test JSON parse failure degrades to final_answer (raw text returned as summary)
- [ ] T006 [P] Write failing unit tests for `structured_output()` in `tests/unit/test_claude_backend.py`:
  test valid JSON matching ProposalModel schema → model validates;
  test first call invalid JSON, second call valid JSON → succeeds on retry;
  test both calls invalid JSON → raises RuntimeError("Claude structured output failed after 2 attempts")

### Implementation

- [ ] T007 Implement `src/agent/claude_backend.py` to make T004–T006 pass:
  - `ToolCall` and `ClaudeResponse` dataclasses (from data-model.md)
  - `call_claude(prompt: str, *, timeout: int = 120) -> str` (subprocess wrapper per contracts/claude-cli.md)
  - `research_loop(system_prompt: str, user_prompt: str, tools: dict[str, Callable], max_tool_calls: int = 4) -> str`
  - `structured_output(prompt: str, schema: type[BaseModel]) -> dict[str, Any]`

**Checkpoint**: `uv run python -m pytest tests/unit/test_claude_backend.py` — all pass → foundation ready

---

## Phase 3: User Story 1 — Run Without Azure (Priority: P1) 🎯 MVP

**Goal**: Agent researches and proposes a triage action using Claude CLI, with no Azure, LangSmith, or Anthropic API key.

**Independent Test**: From a clean environment with only `GITHUB_TOKEN` set (no Azure env vars), call `triager.research_issue()` + `triager.propose_action()` with a mock stale issue — verify a valid `ProposalModel` dict is returned.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementing `triager.py`**

- [ ] T008 [P] [US1] Write failing integration test for `research_issue()` in `tests/integration/test_triager.py`:
  fixture: mock `GitHubClient` returning a sample issue dict;
  mock `claude_backend.research_loop` returning a research summary string;
  assert `state.research_summary` is set and non-empty
- [ ] T009 [P] [US1] Write failing integration test for `propose_action()` in `tests/integration/test_triager.py`:
  fixture: State with issue + research_summary;
  mock `claude_backend.structured_output` returning valid ProposalModel JSON dict;
  assert `state.proposal` contains expected fields (`close_issue`, `rationale`, etc.)

### Implementation for User Story 1

- [ ] T010 [US1] Update `src/agent/research_prompt.md.jinja2` — prepend tool-call JSON protocol block at top:
  Shape A (`{"type":"tool_call","tool":"...","args":{...}}`),
  Shape B (`{"type":"final_answer","content":"..."}`),
  available tool descriptions in structured list;
  keep existing research instructions below the protocol block
- [ ] T011 [US1] Update `src/agent/propose_action_prompt.md.jinja2` — prepend two-line header:
  `"Respond ONLY with a valid JSON object. No markdown, no explanation."` and
  `"Schema: {{ schema_json }}"` (Jinja2 variable injected from `ProposalModel.model_json_schema()`)
- [ ] T012 [US1] Create `src/agent/triager.py` with:
  - `State` dataclass (same fields as existing in graph.py)
  - `ProposalModel` Pydantic model (moved from graph.py)
  - `TOOLS: dict[str, Callable]` registry (7 GitHub tools, same signatures as current graph.py `@tool` functions but plain `async def`)
  - `select_stale_issue(state: State, client: GitHubClient) -> None` (mirrors existing node)
  - `research_issue(state: State, active_issue_number: int) -> None` (calls `claude_backend.research_loop`)
  - `propose_action(state: State, client: GitHubClient) -> None` (calls `claude_backend.structured_output`)
  - `run(state: State, client: GitHubClient) -> None` stub (wires phases together, calls review later)
- [ ] T013 [US1] Remove `src/agent/graph.py` (delete file) — all logic is now in `triager.py` and `claude_backend.py`

**Checkpoint**: `uv run python -m pytest tests/integration/test_triager.py::test_research_issue tests/integration/test_triager.py::test_propose_action` — pass → US1 independently functional

---

## Phase 4: User Story 2 — Simplified Setup (Priority: P2)

**Goal**: New contributor can clone and run the agent without any Azure account, Azure CLI, or LangSmith credentials.

**Independent Test**: README and pyproject.toml contain no Azure references. Running `uv run python src/agent/main.py` with only `GITHUB_TOKEN` set produces no "missing Azure credential" errors.

- [ ] T014 [P] [US2] Update `README.md`:
  - Remove "Configuring Azure AI models" section entirely
  - Remove "Running the stale issue closer" section (LangGraph dev server)
  - Remove "Agent Inbox setup" section
  - Add "Prerequisites" section: Python 3.11+, uv, Claude Code CLI, Claude Max/Pro subscription
  - Add "Configuring Claude" section: `claude auth status` check, `claude auth login` if needed
  - Update "Running the triager" section: `uv run python src/agent/main.py`
  - Update "Cost estimate" section: subscription cost replaces per-token Azure pricing
  - Keep: "Getting started", "Configuring GitHub authentication", "Developer tasks", "Resources"
- [ ] T015 [P] [US2] Remove Azure-related env vars from `.env.example` (if file exists); if file does not exist, create `.env.example` with only `GITHUB_TOKEN` and `TARGET_REPO`

**Checkpoint**: README has no `azd`, `AZURE_*`, `LANGSMITH_*` references → US2 done

---

## Phase 5: User Story 3 — Human Review Preserved (Priority: P3)

**Goal**: Agent still pauses for human approval before every GitHub write action. Reviewer can accept, edit, skip, or quit via terminal prompt.

**Independent Test**: Call `triager.review_issue()` with a mock proposal and mock stdin input of `a` (accept) — verify `ReviewDecision.approved == True` and fields match proposal. Call again with `s` (skip) — verify `ReviewDecision.approved == False`. Call `apply_decision()` with an approved decision and mock GitHubClient — verify `close_issue()` and `post_comment()` called. Call with non-approved decision — verify NO GitHub methods called.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementing review/apply**

- [ ] T016 [P] [US3] Write failing integration tests for `review_issue()` in `tests/integration/test_triager.py`:
  mock `builtins.input` to return `"a"` → ReviewDecision.approved True, fields mirror proposal;
  mock input to return `"s"` → ReviewDecision.approved False;
  mock input to return `"q"` → `SystemExit` raised (or equivalent quit signal);
  mock input for `"e"` path → prompt per-field edits, blank = keep original
- [ ] T017 [P] [US3] Write failing integration tests for `apply_decision()` in `tests/integration/test_triager.py`:
  approved=True, close_issue=True, post_comment="text" → assert `client.close_issue()` and `client.post_comment()` called;
  approved=True, close_issue=False → assert `client.close_issue()` NOT called;
  approved=False → assert NO `client.*` write methods called

### Implementation for User Story 3

- [ ] T018 [US3] Add `review_issue(state: State) -> ReviewDecision` to `src/agent/triager.py`:
  render `review_template.md.jinja2` with proposal fields (reuse existing Jinja2 template);
  print rendered review + `[a]ccept [e]dit [s]kip [q]uit` prompt;
  parse input: `a` → approved=True fields from proposal; `e` → per-field edit loop (blank=keep); `s` → approved=False; `q` → `sys.exit(0)`
- [ ] T019 [US3] Add `apply_decision(decision: ReviewDecision, client: GitHubClient) -> None` to `src/agent/triager.py`:
  if not approved: log "Skipped" and return;
  call `client.remove_label()` for each in `decision.remove_labels`;
  call `client.add_label()` for each in `decision.add_labels` (skip any also in remove_labels);
  call `client.post_comment()` if `decision.post_comment`;
  call `client.assign_issue_to_copilot()` if `decision.assign_issue_to_copilot and not decision.close_issue`;
  call `client.close_issue()` if `decision.close_issue`
- [ ] T020 [US3] Create `src/agent/main.py` — entry point:
  `load_dotenv(override=True)`;
  validate `GITHUB_TOKEN` env var present (raise with clear message if missing);
  instantiate `GitHubClient()`;
  instantiate `State()`;
  `asyncio.run(triager.run(state, client))` — `run()` calls all 5 phases in sequence;
  wrap in `try/except RuntimeError` → print `f"Error: {e}"` and `sys.exit(1)`;
  no `if __name__ == "__main__"` guard needed (invoked via `uv run python src/agent/main.py`)
- [ ] T021 [US3] Update `run()` in `src/agent/triager.py` to call all phases:
  `select_stale_issue → research_issue → propose_action → review_issue → apply_decision`

**Checkpoint**: `uv run python -m pytest tests/integration/` — all pass → full end-to-end flow verifiable

---

## Phase N: Polish & Cross-Cutting Concerns

- [ ] T022 [P] Run `uv run -- ruff check .` and `uv run -- ruff format .` — fix all lint/format errors in `claude_backend.py`, `triager.py`, `main.py`
- [ ] T023 [P] Run `uv run -- mypy src` — fix all type errors in new modules
- [ ] T024 Run `uv run -- python -m pytest` — verify full test suite passes (unit + integration)
- [ ] T025 [P] Update `CLAUDE.md` with correct run command (`uv run python src/agent/main.py`) and remove LangGraph server reference

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 complete (especially T001 dep removal) — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Phase 2 complete (needs `claude_backend.py`)
- **User Story 2 (Phase 4)**: Depends only on Phase 1 (docs/config changes, no code dep) — can run in parallel with US1
- **User Story 3 (Phase 5)**: Depends on US1 complete (needs `triager.py` with research+propose)
- **Polish (Phase N)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational (Phase 2)
- **US2 (P2)**: Can start after Phase 1 (Setup) — independent of US1/US3
- **US3 (P3)**: Depends on US1 complete (extends triager.py)

### Within Each User Story

- Tests MUST be written and confirmed FAILING before implementation begins
- Prompt template updates (T010, T011) before triager.py implementation (T012)
- Core module before integration with entry point

### Parallel Opportunities

- T004, T005, T006 run in parallel (different test suites for different functions)
- T008, T009 run in parallel (different test functions)
- T014, T015 run in parallel (different files)
- T016, T017 run in parallel (different test functions)
- T018, T019 run in parallel (different functions in same file — only if no edit conflicts)
- T022, T023, T025 run in parallel (different commands, different files)
- US2 (Phase 4) can run in parallel with US1 (Phase 3) if separate developer

---

## Implementation Strategy

### MVP First (User Stories 1 + 3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (claude_backend.py) — CRITICAL GATE
3. Complete Phase 3: User Story 1 (research + propose via Claude CLI)
4. Complete Phase 5: User Story 3 (review + apply + main.py)
5. **STOP and VALIDATE**: Run `uv run python src/agent/main.py` with a real `GITHUB_TOKEN` and Claude subscription — full flow end-to-end
6. Deploy/share

### Full Delivery

1. MVP above
2. Phase 4: User Story 2 (docs cleanup)
3. Phase N: Polish (lint, type check, full test suite)

---

## Notes

- [P] tasks = different files / no order dependency
- [Story] label maps task to its user story for traceability
- Tests must FAIL before implementation — verify with `uv run python -m pytest <test_file>`
- Constitution Principle I: `apply_decision()` MUST be gated behind `review_issue()` with no bypass path
- `graph.py` is entirely replaced — do not modify it, just delete (T013)
- `github_client.py` is UNCHANGED — do not edit
