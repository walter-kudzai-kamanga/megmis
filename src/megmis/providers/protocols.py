from __future__ import annotations

from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable

from megmis.common.schemas import LatLon


@runtime_checkable
class WeatherProvider(Protocol):
    def get_current(self, lat: float, lon: float) -> dict[str, Any]: ...
    def get_forecast(self, lat: float, lon: float, days: int) -> list[dict[str, Any]]: ...
    def get_hourly(self, lat: float, lon: float, on_date: date) -> list[dict[str, Any]]: ...
    def get_historical(
        self, lat: float, lon: float, start: date, end: date
    ) -> list[dict[str, Any]]: ...
    def get_alerts(self, lat: float, lon: float) -> list[dict[str, Any]]: ...


@runtime_checkable
class RoutingProvider(Protocol):
    def route(
        self,
        origin: LatLon,
        dest: LatLon,
        waypoints: list[LatLon],
        costing_profile: str,
        departure_time: datetime | None,
    ) -> list[dict[str, Any]]: ...

    def matrix(
        self, sources: list[LatLon], targets: list[LatLon], profile: str
    ) -> dict[str, Any]: ...


@runtime_checkable
class GeocodingProvider(Protocol):
    def geocode(self, address: str) -> list[LatLon]: ...
    def reverse(self, lat: float, lon: float) -> dict[str, Any]: ...


@runtime_checkable
class SpeechProvider(Protocol):
    """STT/TTS adapter (Gen 3). lang: en | sn (Shona) | nd (Ndebele)."""

    def stt(self, audio_bytes: bytes, lang: str = "en", *, mime: str = "audio/wav") -> dict[str, Any]:
        """Return {text, lang, confidence, provider, duration_ms?}."""
        ...

    def tts(self, text: str, lang: str = "en", voice: str | None = None) -> dict[str, Any]:
        """Return {audio_bytes, mime, lang, provider, voice}."""
        ...
