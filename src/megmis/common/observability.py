"""Gen 4 observability — in-process metrics, structured JSON logs, alert hooks."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

_lock = threading.Lock()


@dataclass
class _Counter:
    value: float = 0.0


@dataclass
class _Histogram:
    count: int = 0
    sum_ms: float = 0.0
    buckets: dict[float, int] = field(
        default_factory=lambda: {5: 0, 10: 0, 25: 0, 50: 0, 100: 0, 250: 0, 500: 0, 1000: 0, 5000: 0}
    )

    def observe(self, ms: float) -> None:
        self.count += 1
        self.sum_ms += ms
        for edge in sorted(self.buckets):
            if ms <= edge:
                self.buckets[edge] += 1


class MetricsRegistry:
    def __init__(self) -> None:
        self._counters: dict[str, _Counter] = defaultdict(_Counter)
        self._histograms: dict[str, _Histogram] = defaultdict(_Histogram)
        self._gauges: dict[str, float] = {}
        self._alert_handlers: list[Callable[[dict[str, Any]], None]] = []

    def incr(self, name: str, amount: float = 1.0, **labels: str) -> None:
        key = self._key(name, labels)
        with _lock:
            self._counters[key].value += amount

    def observe(self, name: str, ms: float, **labels: str) -> None:
        key = self._key(name, labels)
        with _lock:
            self._histograms[key].observe(ms)

    def gauge(self, name: str, value: float, **labels: str) -> None:
        key = self._key(name, labels)
        with _lock:
            self._gauges[key] = value

    def on_alert(self, handler: Callable[[dict[str, Any]], None]) -> None:
        self._alert_handlers.append(handler)

    def fire_alert(self, alert: dict[str, Any]) -> None:
        alert = {**alert, "ts": datetime.now(UTC).isoformat()}
        self.incr("alerts_fired", kind=str(alert.get("kind") or "generic"))
        for h in self._alert_handlers:
            try:
                h(alert)
            except Exception:  # noqa: BLE001
                logging.getLogger("megmis.alerts").exception("alert handler failed")

    def snapshot(self) -> dict[str, Any]:
        with _lock:
            return {
                "counters": {k: v.value for k, v in self._counters.items()},
                "gauges": dict(self._gauges),
                "histograms": {
                    k: {
                        "count": h.count,
                        "sum_ms": round(h.sum_ms, 3),
                        "avg_ms": round(h.sum_ms / h.count, 3) if h.count else 0.0,
                        "buckets": dict(h.buckets),
                    }
                    for k, h in self._histograms.items()
                },
            }

    def prometheus(self) -> str:
        lines: list[str] = []
        snap = self.snapshot()
        for k, v in snap["counters"].items():
            lines.append(f'megmis_counter{{name="{k}"}} {v}')
        for k, v in snap["gauges"].items():
            lines.append(f'megmis_gauge{{name="{k}"}} {v}')
        for k, h in snap["histograms"].items():
            lines.append(f'megmis_histogram_count{{name="{k}"}} {h["count"]}')
            lines.append(f'megmis_histogram_sum_ms{{name="{k}"}} {h["sum_ms"]}')
        return "\n".join(lines) + "\n"

    @staticmethod
    def _key(name: str, labels: dict[str, str]) -> str:
        if not labels:
            return name
        parts = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}|{parts}"


metrics = MetricsRegistry()


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", "megmis"),
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
            "request_id": getattr(record, "request_id", None),
            "tenant_id": getattr(record, "tenant_id", None),
            "duration_ms": getattr(record, "duration_ms", None),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Strip None
        return json.dumps({k: v for k, v in payload.items() if v is not None}, default=str)


def configure_structured_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


class Timer:
    def __init__(self, metric: str, **labels: str) -> None:
        self.metric = metric
        self.labels = labels
        self._t0 = 0.0

    def __enter__(self) -> Timer:
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        ms = (time.perf_counter() - self._t0) * 1000.0
        metrics.observe(self.metric, ms, **self.labels)
