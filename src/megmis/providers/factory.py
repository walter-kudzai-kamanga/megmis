from __future__ import annotations

from functools import lru_cache

from megmis.common.errors import ProviderError
from megmis.config import get_settings
from megmis.providers.mock_geocoding import MockGeocodingProvider
from megmis.providers.mock_routing import MockRoutingProvider
from megmis.providers.mock_weather import MockWeatherProvider
from megmis.providers.protocols import (
    GeocodingProvider,
    RoutingProvider,
    SpeechProvider,
    WeatherProvider,
)


@lru_cache
def get_weather_provider() -> WeatherProvider:
    settings = get_settings()
    name = settings.weather_provider.lower()
    if name == "open-meteo":
        from megmis.providers.open_meteo import OpenMeteoWeatherProvider

        return OpenMeteoWeatherProvider()
    if name == "openweather":
        from megmis.providers.openweather import OpenWeatherProvider

        try:
            return OpenWeatherProvider()
        except ProviderError:
            return MockWeatherProvider()
    return MockWeatherProvider()


@lru_cache
def get_routing_provider() -> RoutingProvider:
    settings = get_settings()
    name = settings.routing_provider.lower()
    try:
        if name == "valhalla":
            from megmis.providers.http_routing import ValhallaRoutingProvider

            return ValhallaRoutingProvider()
        if name == "graphhopper":
            from megmis.providers.http_routing import GraphHopperRoutingProvider

            return GraphHopperRoutingProvider()
        if name == "osrm":
            from megmis.providers.http_routing import OSRMRoutingProvider

            return OSRMRoutingProvider()
    except ProviderError:
        return MockRoutingProvider()
    return MockRoutingProvider()


@lru_cache
def get_geocoding_provider() -> GeocodingProvider:
    # Nominatim / Google deferred; mock gazetteer remains Gen 2 default for ZW demos
    return MockGeocodingProvider()


@lru_cache
def get_speech_provider() -> SpeechProvider:
    settings = get_settings()
    name = (settings.speech_provider or "mock").lower()
    if name in {"whisper", "faster-whisper"}:
        try:
            import faster_whisper  # noqa: F401
            from megmis.providers.whisper_speech import WhisperSpeechProvider

            return WhisperSpeechProvider()
        except Exception:
            from megmis.providers.mock_speech import MockSpeechProvider

            return MockSpeechProvider()
    from megmis.providers.mock_speech import MockSpeechProvider

    return MockSpeechProvider()
