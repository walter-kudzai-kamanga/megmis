"""OpenStreetMap Nominatim geocoder — resolves arbitrary place names."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from megmis.common.errors import AppError, ProviderError
from megmis.common.schemas import LatLon
from megmis.common.zimbabwe import KNOWN_PLACES, lookup_place

log = logging.getLogger("megmis.geocode.nominatim")

_CACHE: dict[str, tuple[float, list[LatLon] | dict[str, Any]]] = {}
_CACHE_TTL_S = 3600.0
_LAST_CALL = 0.0


class NominatimGeocodingProvider:
    name = "nominatim"

    def __init__(self) -> None:
        self.base = "https://nominatim.openstreetmap.org"
        self.user_agent = "Mamiriro-MEGMIS/0.1 (voice-lab; local-dev)"

    def _throttle(self) -> None:
        global _LAST_CALL
        elapsed = time.monotonic() - _LAST_CALL
        if elapsed < 1.05:
            time.sleep(1.05 - elapsed)
        _LAST_CALL = time.monotonic()

    def _cached(self, key: str):
        hit = _CACHE.get(key)
        if not hit:
            return None
        ts, val = hit
        if time.monotonic() - ts > _CACHE_TTL_S:
            _CACHE.pop(key, None)
            return None
        return val

    def _store(self, key: str, val: list[LatLon] | dict[str, Any]) -> None:
        _CACHE[key] = (time.monotonic(), val)

    def geocode(self, address: str) -> list[LatLon]:
        q = (address or "").strip()
        if not q:
            raise AppError("INVALID_LOCATION", "Empty address", status_code=400)

        # Prefer local gazetteer when it knows the place
        local = lookup_place(q)
        if local:
            return [LatLon(lat=local[0], lon=local[1])]

        # Append Zimbabwe bias if not already country-qualified
        query = q
        low = q.lower()
        if "zimbabwe" not in low and "zambia" not in low and "south africa" not in low:
            query = f"{q}, Zimbabwe"

        ck = f"fwd:{query.lower()}"
        cached = self._cached(ck)
        if cached is not None:
            return list(cached)  # type: ignore[arg-type]

        self._throttle()
        try:
            with httpx.Client(timeout=12.0) as client:
                r = client.get(
                    f"{self.base}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "limit": 3,
                        "addressdetails": 0,
                    },
                    headers={"User-Agent": self.user_agent},
                )
                r.raise_for_status()
                rows = r.json()
        except Exception as exc:  # noqa: BLE001
            log.warning("nominatim geocode failed for %r: %s", q, exc)
            raise ProviderError(f"geocode failed: {exc}", retryable=True) from exc

        if not rows:
            # last resort: try without Zimbabwe suffix
            if query != q:
                return self._geocode_raw(q)
            raise AppError("INVALID_LOCATION", f"Unknown location: {address}", status_code=404)

        points = [LatLon(lat=float(row["lat"]), lon=float(row["lon"])) for row in rows]
        self._store(ck, points)
        # remember best hit under the original query for later lookups
        if points:
            KNOWN_PLACES.setdefault(q.strip().lower(), (points[0].lat, points[0].lon))
        return points

    def _geocode_raw(self, q: str) -> list[LatLon]:
        ck = f"fwd:{q.lower()}"
        cached = self._cached(ck)
        if cached is not None:
            return list(cached)  # type: ignore[arg-type]
        self._throttle()
        try:
            with httpx.Client(timeout=12.0) as client:
                r = client.get(
                    f"{self.base}/search",
                    params={"q": q, "format": "json", "limit": 3},
                    headers={"User-Agent": self.user_agent},
                )
                r.raise_for_status()
                rows = r.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"geocode failed: {exc}", retryable=True) from exc
        if not rows:
            raise AppError("INVALID_LOCATION", f"Unknown location: {q}", status_code=404)
        points = [LatLon(lat=float(row["lat"]), lon=float(row["lon"])) for row in rows]
        self._store(ck, points)
        if points:
            KNOWN_PLACES.setdefault(q.strip().lower(), (points[0].lat, points[0].lon))
        return points

    def reverse(self, lat: float, lon: float) -> dict[str, Any]:
        ck = f"rev:{lat:.5f},{lon:.5f}"
        cached = self._cached(ck)
        if cached is not None:
            return dict(cached)  # type: ignore[arg-type]
        self._throttle()
        try:
            with httpx.Client(timeout=12.0) as client:
                r = client.get(
                    f"{self.base}/reverse",
                    params={"lat": lat, "lon": lon, "format": "json"},
                    headers={"User-Agent": self.user_agent},
                )
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"reverse geocode failed: {exc}", retryable=True) from exc
        out = {
            "address": data.get("display_name") or f"{lat},{lon}",
            "components": data.get("address") or {},
            "lat": lat,
            "lon": lon,
        }
        self._store(ck, out)
        return out
