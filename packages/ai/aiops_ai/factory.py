"""Choose the right AI provider for the current configuration.

Call `get_provider()` — never construct a provider class directly. That keeps
the Demo Mode / live / bring-your-own-key decision in one place.
"""

from __future__ import annotations

from typing import Protocol

from aiops_ai.base import AIProvider
from aiops_ai.providers.anthropic_provider import AnthropicProvider
from aiops_ai.providers.demo import DemoProvider
from aiops_ai.providers.gemini_provider import GeminiProvider
from aiops_ai.providers.openai_provider import OpenAIProvider
from aiops_config import ProviderName, Settings, get_settings


class _LiveProviderFactory(Protocol):
    """The constructor signature every live (non-demo) provider shares.

    `AIProvider` itself declares no `__init__`, so this protocol is what lets
    the registry below be typed precisely.
    """

    def __call__(self, settings: Settings, *, api_key: str | None = None) -> AIProvider: ...


_LIVE_PROVIDERS: dict[ProviderName, _LiveProviderFactory] = {
    ProviderName.ANTHROPIC: AnthropicProvider,
    ProviderName.OPENAI: OpenAIProvider,
    ProviderName.GEMINI: GeminiProvider,
}


def get_provider(
    settings: Settings | None = None,
    *,
    provider: ProviderName | None = None,
    api_key: str | None = None,
) -> AIProvider:
    """Return the AI provider to use for this request.

    Resolution order:
      1. `api_key` supplied  -> live provider ("bring your own key", Section 3b).
      2. `DEMO_MODE=true`    -> DemoProvider, replaying recorded outputs.
      3. otherwise           -> the configured live provider.
    """
    settings = settings or get_settings()
    chosen = provider or settings.ai_provider

    if api_key:
        if not settings.allow_bring_your_own_key:
            from aiops_utils import ConfigurationError

            raise ConfigurationError(
                "Bring-your-own-key is disabled (ALLOW_BRING_YOUR_OWN_KEY=false)."
            )
        return _LIVE_PROVIDERS[chosen](settings, api_key=api_key)

    if settings.demo_mode:
        return DemoProvider()

    return _LIVE_PROVIDERS[chosen](settings)


def get_embedding_provider(
    settings: Settings | None = None, *, api_key: str | None = None
) -> AIProvider:
    """Provider for `generate_embeddings()`.

    Separate from `get_provider()` because Anthropic has no embeddings endpoint,
    so semantic search may need a different provider than chat does.
    """
    settings = settings or get_settings()
    if settings.demo_mode and not api_key:
        return DemoProvider()
    return _LIVE_PROVIDERS[settings.embedding_provider](settings, api_key=api_key)


def get_transcription_provider(
    settings: Settings | None = None, *, api_key: str | None = None
) -> AIProvider:
    """Provider for `transcribe()` — Whisper by default, for the same reason."""
    settings = settings or get_settings()
    if settings.demo_mode and not api_key:
        return DemoProvider()
    return _LIVE_PROVIDERS[settings.transcribe_provider](settings, api_key=api_key)
