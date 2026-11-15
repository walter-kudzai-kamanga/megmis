from __future__ import annotations

from functools import lru_cache

from megmis.providers.orchestrator import get_orchestrator
from megmis.providers.protocols import (
    GeocodingProvider,
    RoutingProvider,
    SpeechProvider,
    WeatherProvider,
)


@lru_cache
def get_weather_provider() -> WeatherProvider:
    return get_orchestrator().get_provider("weather")  # type: ignore[return-value]


@lru_cache
def get_routing_provider() -> RoutingProvider:
    return get_orchestrator().get_provider("routing")  # type: ignore[return-value]


@lru_cache
def get_geocoding_provider() -> GeocodingProvider:
    return get_orchestrator().get_provider("geocode")  # type: ignore[return-value]


@lru_cache
def get_speech_provider() -> SpeechProvider:
    return get_orchestrator().get_provider("speech")  # type: ignore[return-value]


def clear_provider_caches() -> None:
    get_weather_provider.cache_clear()
    get_routing_provider.cache_clear()
    get_geocoding_provider.cache_clear()
    get_speech_provider.cache_clear()
