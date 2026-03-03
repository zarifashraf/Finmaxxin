from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import Principal, PrincipalDep, ServiceContainer, ServicesDep, require_scenario_owner
from app.models.contracts import (
    ActionExecuteRequest,
    AdvisorBriefResponse,
    ActionPreviewRequest,
    DecisionTrace,
    RecommendationListResponse,
    ScenarioCreateResponse,
    ScenarioInput,
    ScenarioRecord,
    SimulationResult,
)

router = APIRouter(prefix="/v1", tags=["finmaxxin"])


@router.post("/scenarios", response_model=ScenarioCreateResponse, status_code=status.HTTP_201_CREATED)
def create_scenario(payload: ScenarioInput, services: ServiceContainer = ServicesDep, principal: Principal = PrincipalDep) -> ScenarioCreateResponse:
    if payload.user_id != principal.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_id must match authenticated principal")

    snapshot = services.data_provider.get_account_snapshot(payload.user_id, payload.snapshot_overrides)
    scenario = ScenarioRecord(input=payload, snapshot=snapshot)
    services.store.save_scenario(scenario)
    services.event_bus.emit("scenario_created", {"scenario_id": scenario.scenario_id, "user_id": payload.user_id})
    return ScenarioCreateResponse(
        scenario_id=scenario.scenario_id,
        created_at=scenario.created_at,
        snapshot=snapshot,
    )


@router.post("/scenarios/{scenario_id}/simulate", response_model=SimulationResult)
def simulate_scenario(
    scenario_id: str,
    services: ServiceContainer = ServicesDep,
    principal: Principal = PrincipalDep,
) -> SimulationResult:
    scenario = services.store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scenario not found")
    require_scenario_owner(principal, scenario.input.user_id)

    simulation = services.simulation_service.run(
        scenario_id=scenario_id,
        scenario_input=scenario.input,
        snapshot=scenario.snapshot,
    )
    services.store.save_simulation(simulation)
    services.event_bus.emit("simulation_completed", {"scenario_id": scenario_id, "decision_id": simulation.decision_id})
    return simulation


@router.get("/scenarios/{scenario_id}/recommendations", response_model=RecommendationListResponse)
def get_recommendations(
    scenario_id: str,
    services: ServiceContainer = ServicesDep,
    principal: Principal = PrincipalDep,
) -> RecommendationListResponse:
    scenario = services.store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scenario not found")
    require_scenario_owner(principal, scenario.input.user_id)

    simulation = services.store.get_simulation(scenario_id)
    if simulation is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scenario must be simulated first")

    recs = services.store.get_recommendations(scenario_id)
    if not recs:
        raw_recs, feature_contributions = services.recommendation_service.rank(scenario.input, simulation)
        policy_checks: list[dict] = []
        filtered = []
        for rec in raw_recs:
            allowed, checks = services.policy_service.evaluate(rec, scenario.input, scenario.snapshot)
            policy_checks.extend([{"recommendation_id": rec.recommendation_id, **check} for check in checks])
            if allowed:
                filtered.append(rec)

        recs = filtered[:3]
        services.store.save_recommendations(scenario_id, recs)
        trace = services.transparency_service.build_trace(scenario, simulation, feature_contributions, policy_checks)
        services.store.save_trace(trace)

    services.event_bus.emit("recommendation_viewed", {"scenario_id": scenario_id, "recommendation_count": len(recs)})
    return RecommendationListResponse(scenario_id=scenario_id, recommendations=recs)


@router.post("/scenarios/{scenario_id}/advisor-brief", response_model=AdvisorBriefResponse)
def get_advisor_brief(
    scenario_id: str,
    services: ServiceContainer = ServicesDep,
    principal: Principal = PrincipalDep,
) -> AdvisorBriefResponse:
    scenario = services.store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scenario not found")
    require_scenario_owner(principal, scenario.input.user_id)

    simulation = services.store.get_simulation(scenario_id)
    if simulation is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scenario must be simulated first")

    brief = services.advisory_orchestrator_service.generate_brief(scenario, simulation)
    return brief


@router.post("/actions/preview")
def preview_action(
    payload: ActionPreviewRequest,
    services: ServiceContainer = ServicesDep,
    principal: Principal = PrincipalDep,
):
    scenario = services.store.get_scenario(payload.scenario_id)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scenario not found")
    require_scenario_owner(principal, scenario.input.user_id)

    recommendations = services.store.get_recommendations(payload.scenario_id)
    recommendation = next((r for r in recommendations if r.recommendation_id == payload.recommendation_id), None)
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="recommendation not found")
    if recommendation.action_type != payload.action_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="action_type mismatch")

    preview = services.execution_service.preview(recommendation)
    services.store.save_preview(preview)
    services.event_bus.emit("action_confirmed", {"scenario_id": payload.scenario_id, "action_id": preview.action_id})
    return preview


@router.post("/actions/execute")
def execute_action(
    payload: ActionExecuteRequest,
    services: ServiceContainer = ServicesDep,
    principal: Principal = PrincipalDep,
):
    preview = services.store.get_preview(payload.preview_id)
    if preview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="preview_id not found")

    scenario = next(
        (s for s in services.store.scenarios.values() if payload.action_id in {r.recommendation_id for r in services.store.get_recommendations(s.scenario_id)}),
        None,
    )
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scenario for action not found")
    require_scenario_owner(principal, scenario.input.user_id)

    try:
        result = services.execution_service.execute(payload)
    except HTTPException as exc:
        services.event_bus.emit(
            "execution_failed",
            {"action_id": payload.action_id, "preview_id": payload.preview_id, "reason": str(exc.detail)},
        )
        raise

    services.event_bus.emit("action_executed", {"action_id": payload.action_id, "execution_id": result.execution_id})
    return result


@router.get("/decisions/{decision_id}/trace", response_model=DecisionTrace)
def get_decision_trace(
    decision_id: str,
    services: ServiceContainer = ServicesDep,
    principal: Principal = PrincipalDep,
) -> DecisionTrace:
    trace = services.store.get_trace(decision_id)
    if trace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="decision trace not found")

    scenario = services.store.get_scenario(trace.scenario_id)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scenario not found")
    require_scenario_owner(principal, scenario.input.user_id)
    return trace


@router.get("/events")
def list_events(services: ServiceContainer = ServicesDep):
    return {"events": services.store.events}
