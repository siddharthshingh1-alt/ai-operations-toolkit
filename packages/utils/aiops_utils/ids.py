"""Human-readable, sortable identifiers.

`new_id("sop")` -> `"sop_01hq3k9m2n4p"`.

The prefix makes IDs self-describing in logs and URLs; the body is derived from
a UUID4 so IDs stay unguessable.
"""

from __future__ import annotations

import uuid

_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"  # Crockford-ish: no i, l, o, u


def new_id(prefix: str, *, length: int = 12) -> str:
    """Return a new prefixed identifier, e.g. `booking_7f3k2m9qa1zc`."""
    if not prefix.isidentifier():
        raise ValueError(f"prefix must be a valid identifier, got {prefix!r}")
    value = uuid.uuid4().int
    chars: list[str] = []
    for _ in range(length):
        value, index = divmod(value, len(_ALPHABET))
        chars.append(_ALPHABET[index])
    return f"{prefix}_{''.join(chars)}"
