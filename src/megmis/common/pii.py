"""Gen 4 PII rules — pseudonymise voice transcripts / reporter refs; scrub logs."""

from __future__ import annotations

import hashlib
import re
from typing import Any

# Rough patterns for phone / email / national-id-ish tokens in free text
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"\b(?:\+?263|0)\d{8,10}\b")
_LONG_DIGIT = re.compile(r"\b\d{8,}\b")


def rotating_pseudonym(value: str, *, salt: str = "megmis-pii", length: int = 12) -> str:
    digest = hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()
    return f"anon_{digest[:length]}"


def redact_transcript(text: str | None, *, salt: str = "megmis-pii") -> str:
    if not text:
        return ""
    out = _EMAIL.sub(lambda m: rotating_pseudonym(m.group(0), salt=salt), text)
    out = _PHONE.sub(lambda m: rotating_pseudonym(m.group(0), salt=salt), out)
    out = _LONG_DIGIT.sub(lambda m: rotating_pseudonym(m.group(0), salt=salt), out)
    return out


def scrub_log_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop or hash fields that must never appear in structured logs."""
    banned = {"transcript", "raw_transcript", "audio_b64", "api_key", "password", "secret"}
    clean: dict[str, Any] = {}
    for k, v in payload.items():
        lk = k.lower()
        if lk in banned or "transcript" in lk or lk.endswith("_secret"):
            if isinstance(v, str) and v:
                clean[k] = rotating_pseudonym(v)
            else:
                clean[k] = "[redacted]"
        elif isinstance(v, dict):
            clean[k] = scrub_log_fields(v)
        else:
            clean[k] = v
    return clean
