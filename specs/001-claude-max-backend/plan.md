# Implementation Plan: Claude Max/Pro Backend

**Branch**: `001-claude-max-backend` | **Date**: 2026-06-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-claude-max-backend/spec.md`

## Summary

Replace Azure OpenAI / GitHub Models LLM backend with the Claude Code CLI (`claude`), using the user's existing Max or Pro subscription. Remove LangGraph, LangChain, LangSmith, and Azure Identity dependencies. Preserve all GitHub investigation capabilities and the human-in-the-loop review gate via a new interactive CLI review step. The result is a simpler Python script that calls the `claude` CLI as a subprocess for LLM work and uses a terminal prompt for human review.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies (keep)**: `httpx`, `jinja2`, `pydantic`, `python-dotenv`
**Primary Dependencies (remove)**: `langgraph`, `langgraph-sdk`, `langgraph-cli`, `langchain`, `langchain-openai`, `azure-identity`
**Primary Dependencies (add)**: none — `claude` CLI is a system binary already installed with the Claude Code subscription; accessed via `subprocess`
**Storage**: N/A (stateless per-run; no persistence layer)
**Testing**: pytest (existing dev dependency)
**Target Platform**: Any OS where Claude Code CLI is installed and authenticated with a Max or Pro subscription
**Project Type**: CLI tool — invoked directly via `uv run python src/agent/main.py`
**Performance Goals**: Single issue triage (select → research → propose → review → apply) in under 90 seconds
**Constraints**:
- `claude` binary MUST be on PATH and authenticated with a valid Max/Pro subscription
- `GITHUB_TOKEN` env var with `repo` scope still required
- No Azure credentials, LangSmith credentials, or Anthropic API key should be needed

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Human-in-the-Loop First | ✅ PASS | CLI review step implemented before every GitHub write action |
| II. Responsible Automation | ✅ PASS | Same issue investigation depth; uncertainty surfaced in proposal |
| III. Test-First Development | ⚠️ DEFERRED | No tests exist yet; tests MUST be added for new modules (see Phase 1) |
| IV. Observability | ✅ PASS | Python `logging` replaces LangSmith; structured per-run log output |
| V. Simplicity | ✅ IMPROVED | Removing 4 heavy deps (langgraph/langchain/azure/langgraph-sdk) REDUCES complexity |

**Constitution Check Post-Design**: Re-evaluate Principle III after research.md is complete and test surface is defined.

## Project Structure

### Documentation (this feature)

```text
specs/001-claude-max-backend/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── claude-cli.md    # Claude subprocess interface contract
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code Changes

```text
src/agent/
├── github_client.py          # UNCHANGED — pure GitHub API, no LLM
├── graph.py                  # REMOVED (or gutted) — LangGraph entry point
├── main.py                   # NEW — CLI entry point replacing `langgraph dev`
├── claude_backend.py         # NEW — Claude CLI subprocess wrapper (tool loop + structured output)
├── triager.py                # NEW — orchestration logic (select → research → propose → review → apply)
├── review_template.md.jinja2 # UNCHANGED — reused for CLI display
├── research_prompt.md.jinja2 # UNCHANGED (minor edits for Claude tool-call format)
└── propose_action_prompt.md.jinja2 # UNCHANGED
```

```text
pyproject.toml    # Remove langgraph, langchain*, azure-identity deps
langgraph.json    # REMOVED (replaced by main.py entry point)
README.md         # Updated — remove Azure/LangSmith setup, add Claude CLI setup
```

**Structure Decision**: Single project layout under `src/`. No new top-level directories. All LLM logic isolated in `claude_backend.py` so future LLM swaps touch one file.

## Complexity Tracking

> No violations — this change reduces complexity rather than adding it.
