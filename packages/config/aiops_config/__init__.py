"""Shared configuration for the AI Operations Toolkit.

Every setting comes from environment variables (or the repo-root `.env`), never
from hard-coded values — see CLAUDE.md Section 5 (Privacy) and Section 24.
"""

from aiops_config.paths import (
    data_dir,
    demo_cache_dir,
    generated_data_dir,
    repo_root,
)
from aiops_config.settings import (
    AuthMode,
    ProviderName,
    Settings,
    get_settings,
    reset_settings_cache,
)

__all__ = [
    "AuthMode",
    "ProviderName",
    "Settings",
    "data_dir",
    "demo_cache_dir",
    "generated_data_dir",
    "get_settings",
    "repo_root",
    "reset_settings_cache",
]
