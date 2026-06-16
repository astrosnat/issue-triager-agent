<!--
## Sync Impact Report

**Version change**: (template) → 1.0.0
**Modified principles**: N/A — initial ratification from template
**Added sections**:
  - Core Principles (5 principles)
  - Technical Constraints
  - Development Workflow
  - Governance
**Removed sections**: None
**Templates requiring updates**:
  - ✅ .specify/templates/plan-template.md — Constitution Check section already generic; no update needed
  - ✅ .specify/templates/spec-template.md — No principle-specific references; no update needed
  - ✅ .specify/templates/tasks-template.md — Task structure already aligns with principles; no update needed
**Deferred TODOs**: None — all placeholders resolved
-->

# Issue Triager Agent Constitution

## Core Principles

### I. Human-in-the-Loop First (NON-NEGOTIABLE)

The agent MUST interrupt and await human approval before taking any irreversible action
on GitHub: posting closing comments, applying labels, or closing issues. Autonomous
destructive actions are prohibited. The interrupt/review cycle via Agent Inbox is not
optional and MUST NOT be bypassed in any code path.

**Rationale**: False positives in issue triage cause real harm to open-source contributors.
Human review is the primary safety gate.

### II. Responsible Automation

The agent MUST minimize false positives. When uncertain whether an issue is truly stale,
the agent MUST surface uncertainty in its proposal rather than guess confidently. The agent
MUST NOT take action on issues that have recent activity, open PRs, or clear ongoing
discussion without explicit human override.

**Rationale**: Trust in the system depends on accuracy. One bad close erodes user confidence
more than ten missed stale issues.

### III. Test-First Development

Tests MUST be written before implementation code. The red-green-refactor cycle is
mandatory. Tests MUST fail before implementation begins. `uv run python -m pytest` MUST
pass before any PR is merged. Contract tests for GitHub API interactions and integration
tests for graph behavior are required for new agent capabilities.

**Rationale**: Agent behavior is hard to inspect at runtime; tests are the primary
correctness signal.

### IV. Observability

LangSmith tracing MUST be enabled in all non-test environments. All graph nodes MUST
emit structured log output sufficient to reconstruct a run post-hoc. Errors from GitHub
API calls, LLM calls, or tool invocations MUST be surfaced with enough context to
diagnose without rerunning.

**Rationale**: Agentic systems fail in non-obvious ways. Observability is not optional
overhead — it is the debugging interface.

### V. Simplicity and Single Purpose

The agent does one thing: triage stale GitHub issues for a target repository. Features
MUST NOT be added that expand scope beyond this purpose without amending this
constitution. YAGNI applies strictly. Complexity MUST be justified against a concrete
need, not anticipated future use.

**Rationale**: Scope creep in agentic systems compounds: each new capability adds new
failure modes and new surface area for human-in-the-loop gaps.

## Technical Constraints

- **Runtime**: Python 3.11+, managed via `uv`
- **Agent framework**: LangGraph (graph ID: `agent`)
- **LLM**: Azure OpenAI (configured via `azd provision` + `.env`)
- **GitHub access**: Personal access token with `repo` scope required; stored in `GITHUB_TOKEN`
- **Tracing**: LangSmith required for Agent Inbox integration (`LANGSMITH_TRACING=true`)
- **Default target**: `Azure-samples/azure-search-openai-demo` (overridable via `TARGET_REPO`)
- **Agent Inbox**: Local submodule at `agent-inbox/`; runs on `http://localhost:3000`

All credentials MUST be stored in `.env` (git-ignored). No secrets in source code or
committed configuration.

## Development Workflow

- **Install deps**: `uv sync`
- **Run agent locally**: `uvx --from "langgraph-cli[inmem]" --with-editable . langgraph dev --allow-blocking`
- **Run tests**: `uv run -- python -m pytest`
- **Lint**: `uv run -- ruff check .`
- **Format**: `uv run -- ruff format .`
- **Type check**: `uv run -- mypy src`

All four quality gates (tests, lint, format, type check) MUST pass before merging.
PRs MUST include a description of how the human-in-the-loop path was verified.

## Governance

This constitution supersedes all other stated practices, conventions, or informal
agreements. Amendments MUST:

1. Be proposed as a PR modifying this file
2. Include a version bump per semantic versioning (see below)
3. Include a migration plan if any principle is removed or redefined
4. Be reviewed by at least one maintainer before merge

**Versioning policy**:
- MAJOR: Principle removed, redefined in a backward-incompatible way, or governance restructured
- MINOR: New principle or section added, or existing principle materially expanded
- PATCH: Clarifications, wording fixes, non-semantic refinements

All PRs and code reviews MUST verify compliance with Principle I (human-in-the-loop)
as the primary gate. Violations of Principle I are blocking; violations of other
principles require documented justification in the PR.

**Version**: 1.0.0 | **Ratified**: 2026-06-16 | **Last Amended**: 2026-06-16
