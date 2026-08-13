"""Shared pytest fixtures.

Tests must never depend on the developer's `.env`, so `isolated_settings`
builds a `Settings` object explicitly and clears the module-level caches that
would otherwise leak state between tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from aiops_config import Settings, reset_settings_cache


@pytest.fixture(autouse=True)
def _clear_caches() -> Iterator[None]:
    """Reset cached settings and datasets around every test."""
    from aiops_adapters import clear_dataset_cache

    reset_settings_cache()
    clear_dataset_cache()
    yield
    reset_settings_cache()
    clear_dataset_cache()


@pytest.fixture
def demo_settings() -> Settings:
    """Settings for the default reviewer experience: Demo Mode, no database."""
    return Settings(
        demo_mode=True,
        database_url=None,
        anthropic_api_key=None,
        openai_api_key=None,
        google_api_key=None,
    )


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """An empty demo-cache directory, isolated from the repo's real one."""
    cache = tmp_path / "demo-cache"
    cache.mkdir()
    return cache
