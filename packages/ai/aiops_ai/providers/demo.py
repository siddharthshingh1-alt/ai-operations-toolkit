"""Demo Mode: replay recorded real AI outputs (CLAUDE.md Section 3b).

The distinction that matters, and the reason this file is written the way it is:

    Faking functionality  = inventing an output no model ever produced.  BANNED.
    Demo Mode             = replaying an output a real model really produced.

`DemoProvider` therefore **cannot invent anything**. If a request has no
recording, it raises `DemoRecordingMissing` and tells you how to record one. It
will never fabricate a plausible-looking answer to fill the gap.

Recordings are produced by `RecordingProvider`, which wraps a live provider and
writes each real response to `data/demo-cache/`. See
`scripts/record_demo_outputs.py`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aiops_ai.base import AIProvider
from aiops_ai.types import AIResult, TranscriptResult, Usage
from aiops_config import demo_cache_dir
from aiops_utils import AIOpsError, get_logger

logger = get_logger(__name__)


class DemoRecordingMissing(AIOpsError):
    """No recorded output exists for this request."""

    status_code = 501
    code = "demo_recording_missing"
    default_user_message = (
        "This action has no demo recording yet. Switch off Demo Mode and supply "
        "an API key to run it live."
    )


def cache_key(operation: str, prompt: str, system: str | None) -> str:
    """Stable key for a request.

    Deliberately excludes the model name so a recording made with one model can
    be replayed regardless of which model is configured now — the recording
    still reports the model that actually produced it.
    """
    payload = json.dumps(
        {"operation": operation, "prompt": prompt, "system": system or ""},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


class DemoProvider(AIProvider):
    """Replays recorded real outputs. Never generates anything."""

    name = "demo"

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._cache_dir = cache_dir or demo_cache_dir()

    # ------------------------------------------------------------------ helpers

    def _path_for(self, key: str) -> Path:
        return self._cache_dir / f"{key}.json"

    def _load(self, operation: str, prompt: str, system: str | None) -> AIResult[Any]:
        key = cache_key(operation, prompt, system)
        path = self._path_for(key)
        if not path.is_file():
            raise DemoRecordingMissing(
                f"No demo recording for operation={operation!r} (key={key}). "
                f"Record one with: npm run record-demo -- --operation {operation}"
            )

        record = json.loads(path.read_text(encoding="utf-8"))
        return AIResult[Any](
            value=record["value"],
            provider=record.get("recorded_provider", "unknown"),
            model=record.get("recorded_model", "unknown"),
            duration_ms=record.get("duration_ms", 0),
            usage=Usage(**record.get("usage", {})),
            from_demo_cache=True,
        )

    def available_recordings(self) -> int:
        """How many recordings are on disk. Surfaced on the health endpoint."""
        if not self._cache_dir.is_dir():
            return 0
        return len(list(self._cache_dir.glob("*.json")))

    # --------------------------------------------------------------- primitives

    def _complete_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> AIResult[str]:
        return self._load("complete_text", prompt, system)

    def _complete_json(
        self,
        prompt: str,
        *,
        schema: dict[str, Any],
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> AIResult[dict[str, Any]]:
        return self._load("complete_json", prompt, system)

    def generate_embeddings(self, texts: list[str]) -> AIResult[list[list[float]]]:
        return self._load("embeddings", json.dumps(texts, sort_keys=True), None)

    def transcribe(self, audio_path: str | Path) -> AIResult[TranscriptResult]:
        result = self._load("transcribe", Path(audio_path).name, None)
        return AIResult[TranscriptResult](
            value=TranscriptResult.model_validate(result.value),
            provider=result.provider,
            model=result.model,
            duration_ms=result.duration_ms,
            usage=result.usage,
            from_demo_cache=True,
        )


class RecordingProvider(AIProvider):
    """Wraps a live provider and saves every real response as a recording.

    Used only by `scripts/record_demo_outputs.py` — never in the running app.
    """

    def __init__(self, inner: AIProvider, cache_dir: Path | None = None) -> None:
        self._inner = inner
        self._cache_dir = cache_dir or demo_cache_dir()
        self.name = inner.name

    def _save(self, operation: str, prompt: str, system: str | None, result: AIResult[Any]) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        key = cache_key(operation, prompt, system)
        value = result.value
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")

        record = {
            "key": key,
            "operation": operation,
            "recorded_at": datetime.now(UTC).isoformat(),
            "recorded_provider": result.provider,
            "recorded_model": result.model,
            "duration_ms": result.duration_ms,
            "usage": result.usage.model_dump(),
            # Stored so a human can tell what a recording is for without
            # re-deriving the hash.
            "prompt_preview": prompt[:400],
            "system_preview": (system or "")[:400],
            "value": value,
        }
        self._path(key).write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("recorded demo output", extra={"operation": operation, "key": key})

    def _path(self, key: str) -> Path:
        return self._cache_dir / f"{key}.json"

    def _complete_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> AIResult[str]:
        result = self._inner._complete_text(
            prompt, system=system, model=model, max_tokens=max_tokens
        )
        self._save("complete_text", prompt, system, result)
        return result

    def _complete_json(
        self,
        prompt: str,
        *,
        schema: dict[str, Any],
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> AIResult[dict[str, Any]]:
        result = self._inner._complete_json(
            prompt, schema=schema, system=system, model=model, max_tokens=max_tokens
        )
        self._save("complete_json", prompt, system, result)
        return result

    def generate_embeddings(self, texts: list[str]) -> AIResult[list[list[float]]]:
        result = self._inner.generate_embeddings(texts)
        self._save("embeddings", json.dumps(texts, sort_keys=True), None, result)
        return result

    def transcribe(self, audio_path: str | Path) -> AIResult[TranscriptResult]:
        result = self._inner.transcribe(audio_path)
        self._save("transcribe", Path(audio_path).name, None, result)
        return result
