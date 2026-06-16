# Quickstart: Issue Triager Agent (Claude Max/Pro Backend)

**For**: specs/001-claude-max-backend

---

## Prerequisites

| Requirement | Check |
|-------------|-------|
| Python 3.11+ | `python --version` |
| uv | `uv --version` |
| Claude Code CLI | `claude --version` |
| Claude Max or Pro subscription | authenticated — `claude auth status` |
| GitHub token (`repo` scope) | obtain from GitHub Developer Settings |

---

## Setup (5 minutes)

1. Clone the repo:
   ```bash
   git clone https://github.com/pamelafox/stale-issue-closer-agent
   cd stale-issue-closer-agent
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Create `.env` with your GitHub token:
   ```
   GITHUB_TOKEN=your_personal_access_token
   TARGET_REPO=owner/name   # optional; defaults to Azure-samples/azure-search-openai-demo
   ```

4. Verify Claude CLI is authenticated:
   ```bash
   claude auth status
   ```
   If not authenticated, run `claude auth login` and follow the prompts.

---

## Running the Triager

```bash
uv run python src/agent/main.py
```

The agent will:
1. Find a stale open issue in `TARGET_REPO`
2. Investigate it using GitHub API tools (via Claude)
3. Produce a triage proposal
4. **Pause** and display the proposal for your review
5. Apply your decision (accept / edit / skip) to GitHub

---

## Review Interface

```
═══════════════════════════════════════════════════════
 TRIAGE PROPOSAL — Issue #1234: "Something is broken"
═══════════════════════════════════════════════════════

  close_issue: YES
    └─ Rationale: No activity in 180 days; original reporter did not respond.

  add_labels: [wontfix]
    └─ Rationale: Issue predates current architecture; not actionable.

  post_comment: "Closing due to inactivity. Reopen if still relevant."

  Overall: Issue is clearly stale with no recent engagement.

───────────────────────────────────────────────────────
 [a]ccept  [e]dit  [s]kip  [q]uit
 > 
```

- `a` — accept and apply all proposed actions to GitHub
- `e` — enter edit mode (modify individual fields before applying)
- `s` — skip this issue (no action taken on GitHub)
- `q` — quit the agent immediately

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `claude: command not found` | Install Claude Code CLI from claude.ai/code |
| `Claude CLI not authenticated` | Run `claude auth login` |
| `GITHUB_TOKEN is required` | Add `GITHUB_TOKEN` to `.env` |
| `No stale issues found` | Change `TARGET_REPO` to a repo with stale issues |

---

## Removed from Setup (vs. previous version)

The following steps from the previous Azure-based setup are **no longer needed**:

- ~~Azure account and CLI (`azd`)~~
- ~~`azd provision`~~
- ~~`AZURE_OPENAI_*` environment variables~~
- ~~LangSmith credentials (`LANGSMITH_*`)~~
- ~~Agent Inbox setup (`agent-inbox/` submodule)~~
- ~~`langgraph dev` server~~
