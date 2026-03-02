from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import ServiceContainer
from app.api.routes import router as finmaxxin_router
from app.config import settings
from app.services.advisor_prompt import AdvisorPromptService
from app.services.advisory_orchestrator import AdvisoryOrchestratorService
from app.services.advisory_validation import AdvisoryValidationService
from app.services.data_provider import AccountDataProvider
from app.services.events import EventBus
from app.services.execution import ExecutionService
from app.services.fallback_advisor import DeterministicFallbackAdvisor
from app.services.llm_client import LlmClientService
from app.services.market_data import MarketDataService
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
    event_bus = EventBus(store)
    market_data_service = MarketDataService(settings)
    llm_client_service = LlmClientService(settings)
    advisor_prompt_service = AdvisorPromptService(settings)
    advisory_validation_service = AdvisoryValidationService(settings)
    fallback_advisor_service = DeterministicFallbackAdvisor()
    advisory_orchestrator_service = AdvisoryOrchestratorService(
        settings=settings,
        market_data_service=market_data_service,
        llm_client=llm_client_service,
        prompt_service=advisor_prompt_service,
        validation_service=advisory_validation_service,
        fallback_advisor=fallback_advisor_service,
        event_bus=event_bus,
        store=store,
    )
    services = ServiceContainer(
        settings=settings,
        store=store,
        data_provider=AccountDataProvider(),
        simulation_service=SimulationService(settings),
        recommendation_service=RecommendationService(),
        policy_service=PolicyService(settings.policy_version),
        execution_service=ExecutionService(settings, store),
        transparency_service=TransparencyService(settings),
        market_data_service=market_data_service,
        llm_client_service=llm_client_service,
        advisor_prompt_service=advisor_prompt_service,
        advisory_validation_service=advisory_validation_service,
        fallback_advisor_service=fallback_advisor_service,
        advisory_orchestrator_service=advisory_orchestrator_service,
        event_bus=event_bus,
    )
    app.state.services = services
    app.include_router(finmaxxin_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
