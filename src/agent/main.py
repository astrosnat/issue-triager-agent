import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv(override=True)  # must run before agent imports so TARGET_REPO is set

from agent import triager  # noqa: E402
from agent.github_client import GitHubClient  # noqa: E402
from agent.triager import State  # noqa: E402

if not os.getenv("GITHUB_TOKEN"):
    print("Error: GITHUB_TOKEN environment variable is required.", file=sys.stderr)
    sys.exit(1)

client = GitHubClient()
state = State()

try:
    asyncio.run(triager.run(state, client))
except RuntimeError as exc:
    print(f"Error: {exc}")
    sys.exit(1)
