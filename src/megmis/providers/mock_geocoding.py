from __future__ import annotations

from typing import Any

from megmis.common.errors import AppError
from megmis.common.schemas import LatLon
from megmis.common.zimbabwe import KNOWN_PLACES, lookup_place


class MockGeocodingProvider:
    name = "mock-geocode"

    def geocode(self, address: str) -> list[LatLon]:
        coords = lookup_place(address)
        if coords is None:
            raise AppError("INVALID_LOCATION", f"Unknown location: {address}", status_code=404)
        return [LatLon(lat=coords[0], lon=coords[1])]

    def reverse(self, lat: float, lon: float) -> dict[str, Any]:
        best_name = "Unknown"
        best_dist = float("inf")
        for name, (plat, plon) in KNOWN_PLACES.items():
            dist = (lat - plat) ** 2 + (lon - plon) ** 2
            if dist < best_dist:
                best_dist = dist
                best_name = name.title()
        return {
            "address": f"{best_name}, Zimbabwe",
            "components": {"city": best_name, "country": "Zimbabwe"},
            "lat": lat,
            "lon": lon,
        }
