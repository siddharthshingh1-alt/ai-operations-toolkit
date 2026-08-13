"""Tests for the Gemini schema converter.

These exist because of a real failure: the provider used to describe the
required JSON in the prompt rather than constraining decoding with a schema.
The model mostly complied, and intermittently returned an object with no
closing brace — which surfaced as "invalid JSON" with no obvious cause.

Constraining decoding fixes it, but only if the converted schema is actually
valid for Gemini. That is what these check.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from aiops_ai.base import strict_json_schema
from aiops_ai.providers.gemini_schema import to_gemini_schema


class _Step(BaseModel):
    number: int
    instruction: str


class _Nested(BaseModel):
    title: str
    steps: list[_Step] = Field(default_factory=list)
    note: str | None = None


def test_refs_are_inlined() -> None:
    """Gemini does not resolve `$ref`, so none may survive conversion."""
    converted = to_gemini_schema(strict_json_schema(_Nested))
    assert "$ref" not in json.dumps(converted)
    assert "$defs" not in json.dumps(converted)


def test_nested_model_becomes_an_inline_object() -> None:
    converted = to_gemini_schema(strict_json_schema(_Nested))
    step = converted["properties"]["steps"]["items"]
    assert step["type"] == "object"
    assert set(step["properties"]) == {"number", "instruction"}


def test_additional_properties_is_removed() -> None:
    """Gemini rejects it outright, and `strict_json_schema` always adds it."""
    assert "additionalProperties" in json.dumps(strict_json_schema(_Nested))
    assert "additionalProperties" not in json.dumps(to_gemini_schema(strict_json_schema(_Nested)))


def test_optional_field_becomes_nullable() -> None:
    """Pydantic renders `str | None` as anyOf; Gemini has no anyOf."""
    converted = to_gemini_schema(strict_json_schema(_Nested))
    note = converted["properties"]["note"]
    assert "anyOf" not in note
    assert note.get("nullable") is True
    assert note["type"] == "string"


def test_required_never_names_a_missing_property() -> None:
    converted = to_gemini_schema(strict_json_schema(_Nested))
    assert set(converted.get("required", [])) <= set(converted["properties"])


def test_objects_always_declare_a_type() -> None:
    converted = to_gemini_schema(strict_json_schema(_Nested))
    assert converted["type"] == "object"


def test_the_real_sop_schema_converts() -> None:
    """The schema that actually failed in production."""
    from aiops_sop.schema import SopContent

    converted = to_gemini_schema(strict_json_schema(SopContent))
    assert converted["type"] == "object"
    assert len(converted["properties"]) == 13
    serialised = json.dumps(converted)
    assert "$ref" not in serialised
    assert "additionalProperties" not in serialised


def test_answer_schema_converts() -> None:
    from aiops_sop.search import _AnswerModel

    converted = to_gemini_schema(strict_json_schema(_AnswerModel))
    assert set(converted["properties"]) == {"answered", "answer", "reasoning_summary"}
    assert converted["properties"]["answered"]["type"] == "boolean"


def test_only_keys_gemini_accepts_survive() -> None:
    """An unrecognised key is rejected by the API, so none may pass through."""
    allowed = {
        "type",
        "format",
        "description",
        "nullable",
        "enum",
        "items",
        "properties",
        "required",
        "minItems",
        "maxItems",
    }

    def walk(node: object) -> None:
        if isinstance(node, dict):
            assert set(node) <= allowed, f"unexpected keys: {set(node) - allowed}"
            for key, value in node.items():
                if key == "properties" and isinstance(value, dict):
                    for sub in value.values():
                        walk(sub)
                elif key == "items":
                    walk(value)

    from aiops_sop.schema import SopContent

    walk(to_gemini_schema(strict_json_schema(SopContent)))


def test_a_plain_schema_passes_through_unharmed() -> None:
    simple = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
    assert to_gemini_schema(simple) == simple
