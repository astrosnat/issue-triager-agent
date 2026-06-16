"""Shared pytest fixtures and configuration."""

import os
import pytest


@pytest.fixture(autouse=True)
def github_token_env(monkeypatch):
    """Ensure GITHUB_TOKEN is set so GitHubClient can be instantiated in tests."""
    if not os.getenv("GITHUB_TOKEN"):
        monkeypatch.setenv("GITHUB_TOKEN", "test-token-placeholder")
