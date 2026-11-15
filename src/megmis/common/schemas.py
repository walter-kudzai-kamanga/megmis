from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    forecast_dependent = "forecast-dependent"


class OfficialVsModel(str, Enum):
    official = "official"
    model_derived = "model_derived"
    mixed = "mixed"


class Provenance(BaseModel):
    data_source: str
    confidence: Confidence
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    official_vs_model: OfficialVsModel = OfficialVsModel.model_derived


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class LatLon(BaseModel):
    lat: float
    lon: float


class LocationInput(BaseModel):
    """Accept either coordinates or a named place."""

    lat: float | None = None
    lon: float | None = None
    name: str | None = None

    def has_coords(self) -> bool:
        return self.lat is not None and self.lon is not None


T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    data: T
    provenance: Provenance
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    units: str = "metric"


def new_request_id() -> str:
    return str(uuid4())
