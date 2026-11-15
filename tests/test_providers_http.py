"""Real provider adapter tests — mocked HTTP by default; optional LIVE_PROVIDERS=1."""

from __future__ import annotations

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from megmis.common.schemas import LatLon


def test_open_meteo_parses_current():
    from megmis.providers.open_meteo import OpenMeteoWeatherProvider

    payload = {
        "current": {
            "temperature_2m": 22.0,
            "relative_humidity_2m": 40,
            "precipitation": 0,
            "weather_code": 1,
            "wind_speed_10m": 10.0,
            "visibility": 10000,
        }
    }
    with patch("megmis.providers.open_meteo.httpx.Client") as Client:
        client = MagicMock()
        Client.return_value.__enter__.return_value = client
        client.get.return_value.status_code = 200
        client.get.return_value.raise_for_status = MagicMock()
        client.get.return_value.json.return_value = payload
        p = OpenMeteoWeatherProvider()
        cur = p.get_current(-17.8, 31.0)
    assert cur["temperature_c"] == 22.0
    assert cur["provider"] == "open-meteo"
    assert cur["condition"] == "clouds"


def test_osrm_parses_route():
    from megmis.providers.http_routing import OSRMRoutingProvider

    payload = {
        "code": "Ok",
        "routes": [
            {
                "distance": 12000,
                "duration": 900,
                "legs": [{}],
            }
        ],
    }
    with patch("megmis.providers.http_routing.httpx.Client") as Client:
        client = MagicMock()
        Client.return_value.__enter__.return_value = client
        client.get.return_value.status_code = 200
        client.get.return_value.raise_for_status = MagicMock()
        client.get.return_value.json.return_value = payload
        p = OSRMRoutingProvider()
        routes = p.route(
            LatLon(lat=-17.8, lon=31.0),
            LatLon(lat=-20.1, lon=28.6),
            [],
            "fastest",
            None,
        )
    assert routes
    assert routes[0]["distance_m"] == 12000


def test_valhalla_requires_url(monkeypatch):
    from megmis.common.errors import ProviderError
    from megmis.config import get_settings
    from megmis.providers.http_routing import ValhallaRoutingProvider

    get_settings.cache_clear()
    monkeypatch.setenv("VALHALLA_URL", "")
    get_settings.cache_clear()
    with pytest.raises(ProviderError):
        ValhallaRoutingProvider()
    get_settings.cache_clear()


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("LIVE_PROVIDERS", "").lower() not in {"1", "true", "yes"},
    reason="Set LIVE_PROVIDERS=1 to hit public Open-Meteo / OSRM",
)
def test_live_open_meteo_and_osrm():
    from megmis.providers.http_routing import OSRMRoutingProvider
    from megmis.providers.open_meteo import OpenMeteoWeatherProvider

    w = OpenMeteoWeatherProvider().get_current(-17.8252, 31.0335)
    assert w["temperature_c"] is not None
    routes = OSRMRoutingProvider().route(
        LatLon(lat=-17.8252, lon=31.0335),
        LatLon(lat=-20.1325, lon=28.6265),
        [],
        "fastest",
        datetime.utcnow(),
    )
    assert routes and routes[0]["distance_m"] > 0
