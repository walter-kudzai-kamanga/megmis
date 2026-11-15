from fastapi import APIRouter

from megmis.api.v1 import (
    agents,
    console,
    geo,
    health,
    journeys,
    keys,
    risk,
    roads,
    routes,
    traffic,
    weather,
    webhooks,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(weather.router)
api_router.include_router(geo.router)
api_router.include_router(routes.router)
api_router.include_router(roads.router)
api_router.include_router(journeys.router)
api_router.include_router(risk.router)
api_router.include_router(keys.router)
api_router.include_router(webhooks.router)
api_router.include_router(console.router)
api_router.include_router(traffic.router)
api_router.include_router(agents.router)
