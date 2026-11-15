"""Gen 4 provider failover orchestration with health-gated switch."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from megmis.common.errors import ProviderError
from megmis.common.observability import metrics

log = logging.getLogger("megmis.providers.orchestrator")


@dataclass
class ProviderHealth:
    name: str
    healthy: bool = True
    consecutive_failures: int = 0
    last_error: str | None = None
    last_check_at: str | None = None
    last_success_at: str | None = None
    failover_count: int = 0


@dataclass
class FailoverChain:
    kind: str  # weather | routing | geocode | speech
    primary: str
    fallbacks: list[str] = field(default_factory=list)
    failure_threshold: int = 2
    cool_down_s: float = 60.0


class ProviderOrchestrator:
    """
    Tracks provider health and selects the first healthy name in the chain.
    Engines still call Protocol adapters; factory asks orchestrator which to build.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._health: dict[str, ProviderHealth] = {}
        self._active: dict[str, str] = {}
        self._disabled_until: dict[str, float] = {}
        self._chains: dict[str, FailoverChain] = {}
        self._builders: dict[str, Callable[[], Any]] = {}

    def configure_chain(self, chain: FailoverChain) -> None:
        with self._lock:
            self._chains[chain.kind] = chain
            self._active.setdefault(chain.kind, chain.primary)
            for name in [chain.primary, *chain.fallbacks]:
                self._health.setdefault(name, ProviderHealth(name=name))

    def register_builder(
        self, name: str, builder: Callable[[], Any], *, kind: str | None = None
    ) -> None:
        # Key by kind:name so "mock" weather/routing/speech do not clobber each other.
        key = f"{kind}:{name}" if kind else name
        self._builders[key] = builder

    def _builder_for(self, kind: str, name: str) -> Callable[[], Any] | None:
        return self._builders.get(f"{kind}:{name}") or self._builders.get(name)

    def active(self, kind: str) -> str:
        with self._lock:
            chain = self._chains.get(kind)
            if not chain:
                return "mock"
            return self._active.get(kind) or chain.primary

    def get_provider(self, kind: str) -> Any:
        name = self._select(kind)
        builder = self._builder_for(kind, name)
        if builder is None:
            raise ProviderError(f"no builder for provider {kind}:{name}", retryable=False)
        return builder()

    def invoke(self, kind: str, method: str, *args: Any, **kwargs: Any) -> tuple[Any, Any]:
        """Call ``provider.method`` trying primary then fallbacks on ProviderError.

        Returns ``(result, provider_instance)``. Non-ProviderError exceptions propagate.
        """
        with self._lock:
            chain = self._chains.get(kind)
            candidates = (
                [chain.primary, *chain.fallbacks] if chain else [self._active.get(kind, "mock")]
            )
        last: Exception | None = None
        seen: set[str] = set()
        for name in candidates:
            if not name or name in seen:
                continue
            seen.add(name)
            builder = self._builder_for(kind, name)
            if builder is None:
                continue
            provider = builder()
            try:
                result = getattr(provider, method)(*args, **kwargs)
                self.record_success(name)
                with self._lock:
                    self._active[kind] = name
                return result, provider
            except ProviderError as exc:
                last = exc
                self.record_failure(kind, name, str(exc))
                log.warning("provider %s.%s failed (%s); trying next", name, method, exc)
                continue
        if last is not None:
            raise last
        raise ProviderError(f"no providers available for {kind}.{method}", retryable=False)

    def _select(self, kind: str) -> str:
        with self._lock:
            chain = self._chains.get(kind)
            if not chain:
                return "mock"
            now = time.monotonic()
            candidates = [chain.primary, *chain.fallbacks]
            for name in candidates:
                until = self._disabled_until.get(name, 0.0)
                if until > now:
                    continue
                h = self._health.setdefault(name, ProviderHealth(name=name))
                if h.healthy or name == candidates[-1]:
                    prev = self._active.get(kind)
                    if prev and prev != name:
                        h.failover_count += 1
                        metrics.incr("provider_failover_count", kind=kind, to=name, frm=prev)
                        log.warning("failover %s: %s -> %s", kind, prev, name)
                        metrics.fire_alert(
                            {
                                "kind": "provider_failover",
                                "severity": "warning",
                                "provider_kind": kind,
                                "from": prev,
                                "to": name,
                            }
                        )
                    self._active[kind] = name
                    return name
            # everything unhealthy — stick to primary
            self._active[kind] = chain.primary
            return chain.primary

    def record_success(self, name: str) -> None:
        with self._lock:
            h = self._health.setdefault(name, ProviderHealth(name=name))
            h.healthy = True
            h.consecutive_failures = 0
            h.last_error = None
            h.last_success_at = datetime.now(UTC).isoformat()
            h.last_check_at = h.last_success_at
            metrics.gauge("provider_healthy", 1.0, provider=name)

    def record_failure(self, kind: str, name: str, error: str) -> None:
        with self._lock:
            chain = self._chains.get(kind)
            h = self._health.setdefault(name, ProviderHealth(name=name))
            h.consecutive_failures += 1
            h.last_error = error[:500]
            h.last_check_at = datetime.now(UTC).isoformat()
            threshold = chain.failure_threshold if chain else 2
            if h.consecutive_failures >= threshold:
                h.healthy = False
                cool = chain.cool_down_s if chain else 60.0
                self._disabled_until[name] = time.monotonic() + cool
                metrics.gauge("provider_healthy", 0.0, provider=name)
                metrics.incr("provider_unhealthy", provider=name, kind=kind)
                metrics.fire_alert(
                    {
                        "kind": "provider_down",
                        "severity": "critical",
                        "provider": name,
                        "provider_kind": kind,
                        "error": error[:200],
                    }
                )
                # force re-select next call
                if self._active.get(kind) == name and chain:
                    for fb in chain.fallbacks:
                        if fb != name:
                            self._active[kind] = fb
                            break

    def health_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "active": dict(self._active),
                "chains": {
                    k: {"primary": c.primary, "fallbacks": c.fallbacks}
                    for k, c in self._chains.items()
                },
                "providers": {
                    n: {
                        "healthy": h.healthy,
                        "consecutive_failures": h.consecutive_failures,
                        "last_error": h.last_error,
                        "last_check_at": h.last_check_at,
                        "last_success_at": h.last_success_at,
                        "failover_count": h.failover_count,
                    }
                    for n, h in self._health.items()
                },
            }

    def run_health_probes(self) -> dict[str, Any]:
        """Lightweight probes — mark success/failure without requiring live backends."""
        results = {}
        for kind, _chain in list(self._chains.items()):
            name = self.active(kind)
            builder = self._builder_for(kind, name)
            try:
                if builder is None:
                    raise ProviderError("missing builder", retryable=False)
                provider = builder()
                # optional .health() on adapters
                if hasattr(provider, "health"):
                    provider.health()
                self.record_success(name)
                results[kind] = {"provider": name, "ok": True}
            except Exception as exc:  # noqa: BLE001
                self.record_failure(kind, name, str(exc))
                results[kind] = {"provider": name, "ok": False, "error": str(exc)}
        return results


_orchestrator: ProviderOrchestrator | None = None
_orch_lock = threading.Lock()


def get_orchestrator() -> ProviderOrchestrator:
    global _orchestrator
    with _orch_lock:
        if _orchestrator is None:
            _orchestrator = ProviderOrchestrator()
            _bootstrap(_orchestrator)
        return _orchestrator


def reset_orchestrator() -> None:
    global _orchestrator
    with _orch_lock:
        _orchestrator = None
    try:
        from megmis.providers.factory import clear_provider_caches

        clear_provider_caches()
    except Exception:  # noqa: BLE001
        pass


def _bootstrap(orch: ProviderOrchestrator) -> None:
    from megmis.config import get_settings
    from megmis.providers.mock_geocoding import MockGeocodingProvider
    from megmis.providers.mock_routing import MockRoutingProvider
    from megmis.providers.mock_speech import MockSpeechProvider
    from megmis.providers.mock_weather import MockWeatherProvider

    settings = get_settings()

    def weather_builder(name: str):
        def _b():
            if name == "open-meteo":
                from megmis.providers.open_meteo import OpenMeteoWeatherProvider

                return OpenMeteoWeatherProvider()
            if name == "openweather":
                from megmis.providers.openweather import OpenWeatherProvider

                return OpenWeatherProvider()
            return MockWeatherProvider()

        return _b

    def routing_builder(name: str):
        def _b():
            if name == "valhalla":
                from megmis.providers.http_routing import ValhallaRoutingProvider

                return ValhallaRoutingProvider()
            if name == "graphhopper":
                from megmis.providers.http_routing import GraphHopperRoutingProvider

                return GraphHopperRoutingProvider()
            if name == "osrm":
                from megmis.providers.http_routing import OSRMRoutingProvider

                return OSRMRoutingProvider()
            return MockRoutingProvider()

        return _b

    def geocode_builder(name: str):
        def _b():
            if name in {"nominatim", "osm"}:
                from megmis.providers.nominatim_geocoding import NominatimGeocodingProvider

                return NominatimGeocodingProvider()
            return MockGeocodingProvider()

        return _b

    def speech_builder(name: str):
        def _b():
            if name in {"whisper", "faster-whisper"}:
                from megmis.providers.whisper_speech import WhisperSpeechProvider

                return WhisperSpeechProvider()
            return MockSpeechProvider()

        return _b

    weather_primary = (settings.weather_provider or "mock").lower()
    weather_fallbacks = [
        x.strip()
        for x in (settings.weather_failover or "openweather,mock").split(",")
        if x.strip() and x.strip() != weather_primary
    ]
    # Never promote open-meteo to prod without commercial licence flag
    if weather_primary == "open-meteo" and not settings.open_meteo_commercial_ok:
        log.warning(
            "OPEN_METEO_COMMERCIAL_OK=false — using mock for non-dev weather primary "
            "(free Open-Meteo is non-commercial)"
        )
        if settings.app_env not in {"local", "test", "dev"}:
            weather_primary = "mock"

    orch.configure_chain(
        FailoverChain("weather", weather_primary, weather_fallbacks or ["mock"])
    )
    for n in {weather_primary, *weather_fallbacks, "mock"}:
        orch.register_builder(n, weather_builder(n), kind="weather")

    routing_primary = (settings.routing_provider or "mock").lower()
    routing_fallbacks = [
        x.strip()
        for x in (settings.routing_failover or "osrm,graphhopper,mock").split(",")
        if x.strip() and x.strip() != routing_primary
    ]
    orch.configure_chain(
        FailoverChain("routing", routing_primary, routing_fallbacks or ["mock"])
    )
    for n in {routing_primary, *routing_fallbacks, "mock", "osrm", "valhalla", "graphhopper"}:
        orch.register_builder(n, routing_builder(n), kind="routing")

    geocode_primary = (settings.geocode_provider or "mock").lower()
    geocode_fallbacks = [
        x.strip()
        for x in (settings.geocode_failover or "mock").split(",")
        if x.strip() and x.strip() != geocode_primary
    ]
    orch.configure_chain(
        FailoverChain(
            "geocode",
            geocode_primary,
            geocode_fallbacks or ["mock"],
            failure_threshold=1,
        )
    )
    for n in {geocode_primary, *geocode_fallbacks, "mock", "nominatim"}:
        orch.register_builder(n, geocode_builder(n), kind="geocode")

    speech_primary = (settings.speech_provider or "mock").lower()
    speech_fallbacks = [
        x.strip()
        for x in (settings.speech_failover or "mock").split(",")
        if x.strip() and x.strip() != speech_primary
    ]
    orch.configure_chain(
        FailoverChain("speech", speech_primary, speech_fallbacks or ["mock"])
    )
    for n in {speech_primary, *speech_fallbacks, "mock", "whisper"}:
        orch.register_builder(n, speech_builder(n), kind="speech")