# issue-triager-agent Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-06-16

## Active Technologies

- Python 3.11+ (001-claude-max-backend)
- Claude Code CLI subprocess backend (001-claude-max-backend)
- Pydantic v2, Jinja2, httpx, python-dotenv

## Project Structure

```text
src/
  agent/
    main.py                     # Entry point: uv run python src/agent/main.py
    triager.py                  # Orchestration: select → research → propose → review → apply
    claude_backend.py           # Claude CLI subprocess wrapper + ReAct loop
    github_client.py            # GitHub GraphQL + REST API (unchanged)
    research_prompt.md.jinja2   # Research phase prompt (JSON protocol at top)
    propose_action_prompt.md.jinja2
    review_template.md.jinja2
tests/
  conftest.py                   # autouse GITHUB_TOKEN fixture
  unit/test_claude_backend.py
  integration/test_triager.py
```

## Commands

```bash
# Run the agent
uv run python src/agent/main.py

# Tests
uv run python -m pytest

# Lint / format
uv run -- ruff check .
uv run -- ruff format .

# Type check (new modules only; github_client.py has pre-existing errors)
uv run -- mypy src/agent/claude_backend.py src/agent/triager.py src/agent/main.py
```

## Code Style

Python 3.11+: Follow standard conventions

## Prerequisites

- Claude Code CLI installed and authenticated (`claude auth status`)
- `GITHUB_TOKEN` env var with `repo` scope
- No Azure, Anthropic API key, or LangSmith required

## Recent Changes

- 001-claude-max-backend: Replaced LangGraph/Azure backend with Claude Code CLI subprocess
  - Removed: langgraph, langchain, azure-identity, langgraph-sdk
  - Added: pydantic>=2.0, pytest-asyncio>=0.23
  - New: claude_backend.py (subprocess + ReAct), triager.py (orchestration), main.py (entry point)
  - Deleted: graph.py, langgraph.json

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
