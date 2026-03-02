from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status

from app.config import Settings, settings
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


@dataclass
class ServiceContainer:
    settings: Settings
    store: InMemoryStore
    data_provider: AccountDataProvider
    simulation_service: SimulationService
    recommendation_service: RecommendationService
    policy_service: PolicyService
    execution_service: ExecutionService
    transparency_service: TransparencyService
    market_data_service: MarketDataService
    llm_client_service: LlmClientService
    advisor_prompt_service: AdvisorPromptService
    advisory_validation_service: AdvisoryValidationService
    fallback_advisor_service: DeterministicFallbackAdvisor
    advisory_orchestrator_service: AdvisoryOrchestratorService
    event_bus: EventBus


@dataclass
class Principal:
    user_id: str
    token: str


def get_services(request: Request) -> ServiceContainer:
    return request.app.state.services  # type: ignore[no-any-return]


def get_current_principal(
    authorization: str = Header(default=""),
    x_user_id: str | None = Header(default=None),
) -> Principal:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.replace("Bearer ", "", 1).strip()
    if token != settings.required_bearer_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = (x_user_id or "demo-user").strip()
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user identifier")
    return Principal(user_id=user_id, token=token)


def require_scenario_owner(principal: Principal, scenario_user_id: str) -> None:
    if principal.user_id != scenario_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scenario owner mismatch",
        )


PrincipalDep = Depends(get_current_principal)
ServicesDep = Depends(get_services)
