"""Pytest fixtures. The reusable machinery lives in tests/helpers.py."""
import pytest

from helpers import REPO_ROOT, build_sandbox


@pytest.fixture(scope="session")
def repo_root():
    """The real repository root — read-only for tests."""
    return REPO_ROOT


@pytest.fixture
def sandbox(tmp_path):
    """A throwaway repository copy, fresh for every test."""
    return build_sandbox(tmp_path / "repo")
