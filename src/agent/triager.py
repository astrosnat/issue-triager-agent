"""Orchestration logic: select → research → propose → review → apply.

Uses the claude CLI backend (claude_backend.py) for all LLM calls.
GitHub operations go through github_client.GitHubClient.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from jinja2 import BaseLoader, Environment
from pydantic import BaseModel, Field

from agent.claude_backend import research_loop, structured_output
from agent.github_client import GitHubClient

logger = logging.getLogger(__name__)

TARGET_REPO = os.getenv("TARGET_REPO", "Azure-samples/azure-search-openai-demo")

_jinja_env = Environment(
    loader=BaseLoader(), autoescape=False, trim_blocks=True, lstrip_blocks=True
)

_RESEARCH_PROMPT_PATH = Path(__file__).with_name("research_prompt.md.jinja2")
_PROPOSE_PROMPT_PATH = Path(__file__).with_name("propose_action_prompt.md.jinja2")
_REVIEW_TEMPLATE_PATH = Path(__file__).with_name("review_template.md.jinja2")

_RESEARCH_PROMPT_JINJA = _jinja_env.from_string(
    _RESEARCH_PROMPT_PATH.read_text(encoding="utf-8")
)
_PROPOSE_PROMPT_JINJA = _jinja_env.from_string(
    _PROPOSE_PROMPT_PATH.read_text(encoding="utf-8")
)
_REVIEW_TEMPLATE_JINJA = _jinja_env.from_string(
    _REVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
)


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class State:
    """State threaded through each pipeline phase."""

    issue: dict[str, Any] | None = None
    proposal: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None
    review_note: str | None = None
    research_summary: str | None = None


class ProposalModel(BaseModel):
    """Structured triage proposal produced by the propose_action phase."""

    close_issue: bool = Field(description="Whether the issue should be closed now")
    close_issue_rationale: str | None = Field(default=None)
    add_labels: list[str] = Field(default_factory=list)
    add_labels_rationale: str | None = Field(default=None)
    remove_labels: list[str] = Field(default_factory=list)
    remove_labels_rationale: str | None = Field(default=None)
    assign_issue_to_copilot: bool = Field(
        description="Whether to assign to the Copilot agent"
    )
    assign_issue_to_copilot_rationale: str | None = Field(default=None)
    post_comment: str | None = Field(default=None)
    rationale: str = Field(description="Concise reasoning for the chosen actions")


# ─────────────────────────────────────────────────────────────────────────────
# Tool registry
# ─────────────────────────────────────────────────────────────────────────────


def build_tools(
    client: GitHubClient,
    target_repo: str,
    active_issue_number: int | None = None,
) -> dict[str, Callable]:
    """Return the tool registry as async callables bound to client and repo."""

    async def search_issues(query: str) -> str:
        raw = await client.search_issues_with_bodies(
            target_repo, query_text=query, max_results=6, include_comments=True
        )
        filtered = [it for it in raw if it.get("number") != active_issue_number]
        return json.dumps(filtered[:5])

    async def search_code(query: str) -> str:
        hits = await client.search_codebase(
            target_repo, query_text=query, max_results=10, include_text=False
        )
        return json.dumps([h.__dict__ for h in hits])

    async def search_pull_requests(query: str) -> str:
        pulls = await client.search_pull_requests(
            target_repo, query_text=query, max_results=5
        )
        return json.dumps(pulls)

    async def get_pull_request(pr_number: int) -> str:
        try:
            pr = await client.get_pull_request(target_repo, pr_number)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc)})
        return json.dumps(pr or {})

    async def fetch_file(filename_or_path: str) -> str:
        item = await client.fetch_file(target_repo, filename_or_path, include_text=True)
        return json.dumps(item.__dict__ if item else {})

    async def get_issue(issue_number: int) -> str:
        issue = await client.get_issue(
            target_repo, issue_number, include_comments=True, comments_limit=50
        )
        return json.dumps(issue or {})

    async def list_repository_files(ref: str | None = None) -> str:
        paths = await client.list_repository_files(target_repo, ref=ref)
        return json.dumps(paths)

    return {
        "search_issues": search_issues,
        "search_code": search_code,
        "search_pull_requests": search_pull_requests,
        "get_pull_request": get_pull_request,
        "fetch_file": fetch_file,
        "get_issue": get_issue,
        "list_repository_files": list_repository_files,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline phases
# ─────────────────────────────────────────────────────────────────────────────


async def select_stale_issue(state: State, client: GitHubClient) -> None:
    """Find stale open issues and pick the first one into state.issue."""
    stale_issues = await client.find_stale_open_issues(TARGET_REPO)
    if not stale_issues:
        raise RuntimeError(f"No stale issues found in {TARGET_REPO}.")
    selected = stale_issues[0]
    comments = await client.get_issue_comments(TARGET_REPO, selected.number)
    state.issue = {
        "number": selected.number,
        "title": selected.title,
        "url": selected.url,
        "updated_at": selected.updated_at,
        "created_at": selected.created_at,
        "author": selected.author,
        "labels": selected.labels,
        "body": selected.body,
        "comments": comments,
    }


async def research_issue(
    state: State,
    active_issue_number: int,
    client: GitHubClient | None = None,
) -> None:
    """Research the issue using the claude CLI tool-calling loop."""
    assert state.issue is not None, "Issue must be selected before research."
    issue = state.issue

    system_prompt = _RESEARCH_PROMPT_JINJA.render(
        repo=TARGET_REPO,
        issue={
            "number": issue["number"],
            "title": issue["title"],
            "url": issue["url"],
            "updated_at": issue["updated_at"],
            "labels": issue.get("labels") or [],
            "body": issue.get("body") or "",
            "comments": issue.get("comments") or [],
        },
    )

    tools = build_tools(
        client or GitHubClient(),
        TARGET_REPO,
        active_issue_number=active_issue_number,
    )

    summary = await research_loop(
        system_prompt=system_prompt,
        user_prompt="Research the issue above following the response format instructions.",
        tools=tools,
        max_tool_calls=4,
    )
    state.research_summary = summary


async def propose_action(state: State, client: GitHubClient) -> None:
    """Generate a structured triage proposal from the research summary."""
    assert state.issue is not None, "Issue must be selected before proposal."
    assert state.research_summary is not None, "Research summary required before proposal."

    issue = state.issue
    maintainer_username = await client.get_viewer_login()
    label_meta = await client.get_repository_labels(TARGET_REPO)
    repo_labels = [
        {"name": (lbl.get("name") or ""), "description": (lbl.get("description") or "").strip()}
        for lbl in label_meta
        if lbl.get("name")
    ]

    prompt = _PROPOSE_PROMPT_JINJA.render(
        maintainer_username=maintainer_username,
        repo_labels=sorted(repo_labels, key=lambda x: x["name"]),
        issue_number=issue["number"],
        title=issue["title"],
        url=issue["url"],
        updated_at=issue["updated_at"],
        labels=", ".join(issue["labels"]) if issue.get("labels") else "(none)",
        research_summary=state.research_summary,
    )

    result = structured_output(prompt, ProposalModel)
    state.proposal = result


async def run(state: State, client: GitHubClient) -> None:
    """Run the full pipeline: select → research → propose.

    review_issue and apply_decision are added in US3 (T018–T019).
    """
    await select_stale_issue(state, client)
    await research_issue(state, active_issue_number=state.issue["number"], client=client)  # type: ignore[index]
    await propose_action(state, client)
