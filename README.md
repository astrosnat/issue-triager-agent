# Issue Triager Agent

[![Open in GitHub Codespaces](https://img.shields.io/static/v1?style=for-the-badge&label=GitHub+Codespaces&message=Open&color=brightgreen&logo=github)](https://codespaces.new/pamelafox/stale-issue-closer-agent)
[![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/pamelafox/stale-issue-closer-agent)

An agentic system that proposes closing stale GitHub issues, with a human-in-the-loop review step. It selects stale issues from a target repository, investigates with repository-aware tools using Claude, then pauses for you to approve, edit, skip, or quit before posting a closing comment and closing the issue. Requires a Claude Max or Pro subscription — no API key or Azure account needed.

- Default target repo: `Azure-samples/azure-search-openai-demo` (configurable via `TARGET_REPO`)

Contents

- Getting started
  - GitHub Codespaces
  - VS Code Dev Containers
  - Local environment
- Prerequisites
- GitHub authentication (required)
- Configuring Claude
- Running the triager
- Cost estimate
- Developer tasks
- Resources

## Getting started

1. Make sure the following are installed:

    - Python 3.11+
    - Git
    - [uv](https://docs.astral.sh/uv/) (for dependency management)
    - [Claude Code CLI](https://claude.ai/code) (`claude` available on your `PATH`)

2. Clone the repository:

    ```bash
    git clone https://github.com/pamelafox/stale-issue-closer-agent
    cd stale-issue-closer-agent
    ```

3. Create the virtual environment and install dependencies:

    ```bash
    uv sync
    ```

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.11+ | Required by the agent |
| [uv](https://docs.astral.sh/uv/) | Dependency manager |
| [Claude Code CLI](https://claude.ai/code) | Installed and on `PATH` as `claude` |
| Claude Max or Pro subscription | Active subscription linked to Claude Code |
| GitHub personal access token | `repo` scope — see below |

No Azure account, Anthropic API key, or LangSmith account needed.

## Configuring GitHub authentication

This project requires a GitHub personal access token to call the GitHub GraphQL and REST APIs (for searching issues/code and closing issues).

1. In GitHub Developer Settings, create a personal access token with `repo` scope.

2. Set `GITHUB_TOKEN` in your shell or in the `.env` file:

    ```bash
    export GITHUB_TOKEN=your_personal_access_token
    ```

3. Set the target repository (optional, defaults to `Azure-samples/azure-search-openai-demo`):

    ```bash
    # Full name, e.g., owner/name. Default is Azure-samples/azure-search-openai-demo
    export TARGET_REPO=owner/name
    ```

## Configuring Claude

The triager calls `claude --print <prompt>` as a subprocess. Claude Code CLI must be authenticated with your Max or Pro subscription.

1. Check authentication status:

    ```bash
    claude auth status
    ```

2. If not authenticated, log in:

    ```bash
    claude auth login
    ```

   Follow the browser prompt to link your Claude subscription.

## Running the triager

1. Ensure dependencies are installed and Claude is authenticated (see above).

2. Run the agent:

    ```bash
    uv run python src/agent/main.py
    ```

   The agent will:
   - Select a stale issue from `TARGET_REPO`
   - Research it using repository-aware tools (search issues, code, PRs, files)
   - Generate a triage proposal (close, label, comment, assign to Copilot)
   - Print the proposal and prompt you to `[a]ccept [e]dit [s]kip [q]uit`
   - Apply only if you accept

## Cost estimate

LLM usage is billed against your Claude Max or Pro subscription, not per-token. Each triaged issue consumes subscription capacity roughly equivalent to a moderate-length conversation (research loop + proposal generation). No additional per-call cost beyond your subscription.

## Developer tasks

Common dev tasks are available via `uv`:

- Run tests:

  ```bash
  uv run -- python -m pytest
  ```

- Lint / format:

  ```bash
  uv run -- ruff check .
  uv run -- ruff format .
  ```

- Type checking:

  ```bash
  uv run -- mypy src
  ```

## Resources

- Claude Code CLI: <https://claude.ai/code>
- Claude subscription plans: <https://claude.ai/upgrade>
- GitHub personal access tokens: <https://github.com/settings/tokens>
