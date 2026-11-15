"""Shared Zimbabwe place gazetteer for geocoding / routing demos."""

from __future__ import annotations

import re

# Display-friendly keys (lowercase). Aliases share coordinates.
KNOWN_PLACES: dict[str, tuple[float, float]] = {
    "harare": (-17.8252, 31.0335),
    "bulawayo": (-20.1325, 28.6265),
    "mutare": (-18.9707, 32.6709),
    "victoria falls": (-17.9243, 25.8572),
    "victoria falls, zimbabwe": (-17.9243, 25.8572),
    "vic falls": (-17.9243, 25.8572),
    "gweru": (-19.4500, 29.8167),
    "masvingo": (-20.0637, 30.8276),
    "chitungwiza": (-18.0127, 31.0756),
    # Eastern Highlands — needed for Nyanga / Nyamaropa requests
    "nyanga": (-18.2167, 32.7450),
    "nyanga, zimbabwe": (-18.2167, 32.7450),
    "nyamaropa": (-18.1500, 32.8500),
    "nyamaropa, nyanga": (-18.1500, 32.8500),
    "nyamaropa, nyanga, zimbabwe": (-18.1500, 32.8500),
    "rusape": (-18.5272, 32.1250),
    "marondera": (-18.1853, 31.5519),
    "chinhoyi": (-17.3667, 30.2000),
    "kwekwe": (-18.9281, 29.8149),
    "kadoma": (-18.3333, 29.9167),
    "beira corridor": (-18.9707, 32.6709),  # alias → Mutare hub
}

def display_name(key: str) -> str:
    base = key.split(",")[0].strip()
    return base.title()


def place_keys_longest_first() -> list[str]:
    return sorted(KNOWN_PLACES.keys(), key=len, reverse=True)


def lookup_place(name: str) -> tuple[float, float] | None:
    """Resolve a free-text place; supports nested phrases like 'nyamaropa in nyanga zimbabwe'."""
    if not name or not str(name).strip():
        return None
    t = str(name).strip().lower()
    t = re.sub(r"[.]+$", "", t)
    t = re.sub(r",?\s*zimbabwe\s*$", "", t).strip(" ,")
    if t in KNOWN_PLACES:
        return KNOWN_PLACES[t]
    # longest known key contained in the phrase
    for key in place_keys_longest_first():
        if len(key) < 3:
            continue
        if key in t:
            return KNOWN_PLACES[key]
    # phrase contained in a longer alias key
    for key in place_keys_longest_first():
        if len(t) >= 4 and t in key:
            return KNOWN_PLACES[key]
    return None


def canon_place_name(name: str) -> str | None:
    """Canonical display name if resolvable, else None."""
    if not name or not str(name).strip():
        return None
    t = str(name).strip().lower()
    t = re.sub(r",?\s*zimbabwe\s*$", "", t).strip(" ,")
    if t in KNOWN_PLACES:
        return display_name(t)
    for key in place_keys_longest_first():
        if len(key) < 3:
            continue
        if key in t:
            return display_name(key)
    for key in place_keys_longest_first():
        if len(t) >= 4 and t in key:
            return display_name(key)
    return None
