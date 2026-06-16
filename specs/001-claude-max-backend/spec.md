# Feature Specification: Claude Max/Pro Subscription Backend

**Feature Branch**: `001-claude-max-backend`
**Created**: 2026-06-16
**Status**: Draft
**Input**: User description: "I want to edit the architecture of issue-triager agent so that it works with an existing Claude Max or Pro subscription (not via API)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run Triager Without Azure OpenAI (Priority: P1)

A user who has a Claude Max or Pro subscription but no Azure account (or who does not want
to pay separately for Azure OpenAI usage) can run the issue triager end-to-end without
provisioning any cloud resources beyond what their Claude subscription already provides.
They install dependencies, set a GitHub token, and start the agent — no `azd provision`,
no Azure credentials, no separate API billing.

**Why this priority**: This is the entire motivation for the feature. Everything else is
contingent on eliminating the Azure OpenAI dependency.

**Independent Test**: Can be tested by running the agent from a clean environment that
has only a Claude subscription and a GitHub token — no Azure environment variables set —
and confirming that the agent successfully selects a stale issue, investigates it, and
produces a triage proposal.

**Acceptance Scenarios**:

1. **Given** a user with a Claude Max/Pro subscription and no Azure credentials configured,
   **When** they start the agent,
   **Then** the agent initialises successfully and begins investigating issues without errors
   related to missing Azure configuration.

2. **Given** the agent is running,
   **When** it processes a stale issue,
   **Then** it produces a triage proposal (closing comment draft) using Claude as the LLM,
   indistinguishable in quality from the Azure OpenAI-backed version.

3. **Given** the agent has produced a proposal,
   **When** no Azure or Anthropic API keys are present in the environment,
   **Then** the agent does not crash or degrade — all LLM calls succeed via the subscription.

---

### User Story 2 - Simplified Setup (Priority: P2)

A developer setting up the project for the first time completes the getting-started steps
without needing an Azure account, Azure CLI, or `azd` tooling. The setup guide reflects
the simpler requirements.

**Why this priority**: Reduces onboarding friction for new contributors and users who
already have a Claude subscription.

**Independent Test**: A new contributor can clone the repo, follow the revised setup
instructions, and have the agent running in under 10 minutes without any Azure steps.

**Acceptance Scenarios**:

1. **Given** a fresh clone of the repository,
   **When** a user follows the updated getting-started guide,
   **Then** they do not encounter any step that requires creating an Azure account or
   running `azd provision`.

2. **Given** the simplified setup is complete,
   **When** the user starts the agent,
   **Then** it functions identically to the fully Azure-provisioned setup.

---

### User Story 3 - Human-in-the-Loop Review Preserved (Priority: P3)

The human-in-the-loop review step — where the agent pauses and the user approves, edits,
or rejects the triage proposal before any action is taken on GitHub — continues to work
after the backend change.

**Why this priority**: Principle I of the project constitution is non-negotiable. The
review gate must survive the architectural change.

**Independent Test**: After switching to the Claude backend, the agent still interrupts
before posting to GitHub. A reviewer can approve, edit, or reject the proposal, and the
correct action (or no action) is applied accordingly.

**Acceptance Scenarios**:

1. **Given** the Claude-backed agent has produced a proposal,
   **When** the agent reaches the human-in-the-loop interrupt point,
   **Then** it pauses and does not post to GitHub until the reviewer approves.

2. **Given** a reviewer rejects a proposal,
   **When** they submit their decision,
   **Then** no comment is posted and no issue is closed.

3. **Given** a reviewer approves a proposal,
   **When** they submit their decision,
   **Then** the agent posts the closing comment and closes the issue as originally designed.

---

### Edge Cases

- What happens if the Claude subscription is not authenticated or the session has expired?
  The agent MUST surface a clear, actionable error rather than a cryptic LLM call failure.
- What happens when the target repository has no stale issues?
  Behaviour must be unchanged from the Azure OpenAI version: agent exits gracefully.
- What if the Claude model's output format differs slightly from Azure OpenAI's?
  The agent MUST parse proposals correctly regardless of minor formatting variation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST use the user's existing Claude Max or Pro subscription as the
  sole LLM backend, with no dependency on Azure OpenAI or a separate Anthropic API key.
- **FR-002**: System MUST preserve all existing GitHub investigation capabilities
  (issue search, comment retrieval, code search, label management).
- **FR-003**: System MUST preserve the human-in-the-loop interrupt-and-review step before
  any write action (comment, label, close) is taken on GitHub.
- **FR-004**: System MUST surface a clear, user-actionable error message when Claude
  subscription access is unavailable or unauthenticated.
- **FR-005**: System MUST NOT require Azure account, Azure CLI, `azd` tooling, or any
  Azure environment variables to start or run.
- **FR-006**: System MUST continue to support configuring the target GitHub repository via
  the existing `TARGET_REPO` mechanism.
- **FR-007**: System MUST continue to produce triage proposals of equivalent quality to
  the Azure OpenAI version (same reasoning, same output structure).
- **FR-008**: An alternative human-in-the-loop review interface is acceptable. The Agent
  Inbox / LangSmith dependency is NOT required. The architecture may change freely (e.g.,
  away from LangGraph) provided the human review gate (FR-003) is preserved through
  another mechanism. Simpler setup is preferred over UI continuity.

### Key Entities

- **Triage Proposal**: A structured output containing a closing comment draft, issue
  metadata, and recommended action (close / skip / escalate). Produced by the LLM and
  presented for human review.
- **LLM Backend**: The component responsible for processing investigation context and
  producing triage proposals. Currently Azure OpenAI; this feature replaces it.
- **Review Gate**: The interrupt point where the agent pauses and awaits human decision
  before taking any GitHub write action.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with only a Claude Max/Pro subscription and a GitHub token can run
  the full triager flow (select issue → investigate → propose → review → act) without
  encountering any Azure-related error or configuration step.
- **SC-002**: Setup time for a new user (from clone to first successful agent run) is
  equal to or less than the current Azure-based setup time.
- **SC-003**: 100% of existing acceptance scenarios for the human-in-the-loop review step
  continue to pass after the backend change.
- **SC-004**: Triage proposal quality is subjectively equivalent: a reviewer comparing
  side-by-side proposals from Azure OpenAI and Claude for the same issue cannot
  consistently distinguish a degradation.

## Assumptions

- The user has Claude Code CLI installed and authenticated with their Max or Pro
  subscription on the machine where the agent runs.
- The user still supplies a GitHub personal access token (`GITHUB_TOKEN`) with `repo`
  scope; GitHub access is unchanged.
- LangSmith tracing and the Agent Inbox UI are treated as optional/configurable for now
  pending clarification of FR-008; the review gate itself is non-negotiable (FR-003).
- The target repository default (`Azure-samples/azure-search-openai-demo`) remains
  unchanged; only the LLM backend changes.
- Python 3.11+ and `uv` remain the runtime and dependency management tools.
