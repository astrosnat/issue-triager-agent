import asyncio
import os
import sys

from dotenv import load_dotenv

from agent import triager
from agent.github_client import GitHubClient
from agent.triager import State

load_dotenv(override=True)

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
