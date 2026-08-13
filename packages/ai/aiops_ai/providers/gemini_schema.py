"""Convert a JSON Schema into the dialect Gemini's `response_schema` accepts.

Asking a model for JSON in the prompt is a request, not a guarantee — it
occasionally returns a truncated or unclosed object, which surfaces as a
confusing parse error. Gemini's native `response_schema` constrains decoding
instead, so the response is well-formed by construction.

It does not accept full JSON Schema, though: it rejects `additionalProperties`
and does not resolve `$ref`/`$defs`, which Pydantic emits for any nested model.
This module bridges that gap — inline the references, drop what Gemini rejects,
keep what it understands.
"""

from __future__ import annotations

from typing import Any

#: Keys Gemini's schema dialect understands. Anything else is dropped rather
#: than passed through, because an unknown key is rejected outright.
_ALLOWED = {
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

#: Guards against a self-referential schema turning inlining into infinite
#: recursion. Nothing in this codebase is recursive; this is a safety net.
_MAX_DEPTH = 12


def _resolve_ref(ref: str, defs: dict[str, Any]) -> dict[str, Any]:
    """Look up a local `$ref` such as `#/$defs/ProcedureStep`."""
    name = ref.rsplit("/", 1)[-1]
    return defs.get(name, {})


def _convert(node: Any, defs: dict[str, Any], depth: int) -> Any:
    if depth > _MAX_DEPTH or not isinstance(node, dict):
        return {"type": "string"} if depth > _MAX_DEPTH else node

    # A reference is replaced by the definition it points at.
    if "$ref" in node:
        return _convert(_resolve_ref(node["$ref"], defs), defs, depth + 1)

    # Pydantic renders `str | None` as anyOf[{...}, {"type": "null"}].
    # Gemini has no anyOf, so take the non-null branch and mark it nullable.
    if "anyOf" in node:
        branches = [b for b in node["anyOf"] if b.get("type") != "null"]
        nullable = len(branches) != len(node["anyOf"])
        if not branches:
            return {"type": "string", "nullable": True}
        converted = _convert(branches[0], defs, depth + 1)
        if nullable and isinstance(converted, dict):
            converted["nullable"] = True
        return converted

    out: dict[str, Any] = {}
    for key, value in node.items():
        if key not in _ALLOWED:
            continue  # additionalProperties, title, default, $defs, ...
        if key == "properties" and isinstance(value, dict):
            out[key] = {k: _convert(v, defs, depth + 1) for k, v in value.items()}
        elif key == "items":
            out[key] = _convert(value, defs, depth + 1)
        else:
            out[key] = value

    # Gemini requires every object to declare a type.
    if "properties" in out and "type" not in out:
        out["type"] = "object"

    # `required` must not name a property that no longer exists after conversion.
    if "required" in out and "properties" in out:
        out["required"] = [r for r in out["required"] if r in out["properties"]]
        if not out["required"]:
            del out["required"]

    return out


def to_gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Convert a Pydantic-generated JSON Schema for Gemini's `response_schema`.

    Inlines `$ref`/`$defs`, collapses nullable `anyOf` unions, and strips keys
    Gemini rejects. The result constrains decoding, so the model cannot return
    malformed or truncated JSON.
    """
    defs = schema.get("$defs", {})
    return _convert(schema, defs, depth=0)
