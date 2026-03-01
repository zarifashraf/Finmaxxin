from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import ServiceContainer
from app.api.routes import router as yousim_router
from app.config import settings
from app.services.data_provider import AccountDataProvider
from app.services.events import EventBus
from app.services.execution import ExecutionService
from app.services.policy import PolicyService
from app.services.recommendation import RecommendationService
from app.services.simulation import SimulationService
from app.services.storage import InMemoryStore
from app.services.transparency import TransparencyService


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Personal Financial Digital Twin API prototype",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    store = InMemoryStore()
    services = ServiceContainer(
        settings=settings,
        store=store,
        data_provider=AccountDataProvider(),
        simulation_service=SimulationService(settings),
        recommendation_service=RecommendationService(),
        policy_service=PolicyService(settings.policy_version),
        execution_service=ExecutionService(settings, store),
        transparency_service=TransparencyService(settings),
        event_bus=EventBus(store),
    )
    app.state.services = services
    app.include_router(yousim_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
