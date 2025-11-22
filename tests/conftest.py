"""
Pytest configuration and shared fixtures for green agent tests.

This file provides common test configuration and fixtures that are
available to all test modules in the tests/ directory.
"""

import sys
from pathlib import Path

import pytest

# Add project root to Python path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def project_root():
    """Fixture providing the project root directory path."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def fixtures_dir():
    """Fixture providing the test fixtures directory path."""
    return Path(__file__).parent / "fixtures"
