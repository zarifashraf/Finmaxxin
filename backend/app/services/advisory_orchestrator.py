from __future__ import annotations

from app.config import Settings
from app.models.contracts import AdvisorBriefResponse, AdvisorBriefTrace, ScenarioRecord, SimulationResult
from app.services.advisor_prompt import AdvisorPromptService
from app.services.advisory_validation import AdvisoryValidationService
from app.services.events import EventBus
from app.services.fallback_advisor import DeterministicFallbackAdvisor
from app.services.llm_client import LlmClientService
from app.services.market_data import MarketDataService
from app.services.storage import InMemoryStore


class AdvisoryOrchestratorService:
    def __init__(
        self,
        settings: Settings,
        market_data_service: MarketDataService,
        llm_client: LlmClientService,
        prompt_service: AdvisorPromptService,
        validation_service: AdvisoryValidationService,
        fallback_advisor: DeterministicFallbackAdvisor,
        event_bus: EventBus,
        store: InMemoryStore,
    ) -> None:
        self.settings = settings
        self.market_data_service = market_data_service
        self.llm_client = llm_client
        self.prompt_service = prompt_service
        self.validation_service = validation_service
        self.fallback_advisor = fallback_advisor
        self.event_bus = event_bus
        self.store = store

    def generate_brief(self, scenario: ScenarioRecord, simulation: SimulationResult) -> AdvisorBriefResponse:
        cached = self.store.get_advisor_brief(simulation.decision_id)
        if cached:
            return cached

        market = self.market_data_service.get_snapshot()
        diagnostics = self.fallback_advisor.evaluate(scenario, simulation)
        validation_errors: list[str] = []
        fallback_used = False
        fallback_reason: str | None = None
        advice_text = ""
        model_used = self.settings.llm_model_name

        if not self.settings.enable_advisor_brief:
            fallback_used = True
            fallback_reason = "advisor_brief_disabled"
            model_used = "deterministic-fallback"
        else:
            system_prompt, user_prompt = self.prompt_service.build(scenario, simulation, market)
            attempt = 0
            while attempt <= self.settings.llm_regeneration_attempts:
                try:
                    candidate, generated_model = self.llm_client.generate(system_prompt, user_prompt)
                    valid, errors = self.validation_service.validate(candidate)
                    if valid:
                        advice_text = candidate
                        model_used = generated_model
                        break
                    validation_errors = errors
                    self.event_bus.emit(
                        "advisor_validation_failed",
                        {
                            "scenario_id": scenario.scenario_id,
                            "decision_id": simulation.decision_id,
                            "errors": errors,
                            "attempt": attempt,
                        },
                    )
                    user_prompt = self.prompt_service.build_repair_prompt(candidate, errors)
                except Exception as exc:
                    fallback_reason = f"llm_failure:{exc.__class__.__name__}"
                    break
                attempt += 1

            if not advice_text and validation_errors and fallback_reason is None:
                fallback_reason = "validation_failed_after_retries"

        if not advice_text:
            advice_text = self.fallback_advisor.generate(scenario, simulation, market, diagnostics=diagnostics)
            fallback_used = True
            fallback_reason = fallback_reason or "fallback_used"
            model_used = "deterministic-fallback"

        brief = AdvisorBriefResponse(
            scenario_id=scenario.scenario_id,
            decision_id=simulation.decision_id,
            advice_text=advice_text,
            market_snapshot_date=market.fetched_at,
            llm_model=model_used,
            fallback_used=fallback_used,
            market_data_stale=market.stale,
            fallback_reason=fallback_reason,
            diagnostics=diagnostics,
        )
        trace = AdvisorBriefTrace(
            scenario_id=scenario.scenario_id,
            decision_id=simulation.decision_id,
            prompt_excerpt=(advice_text[:400] if advice_text else ""),
            validation_errors=validation_errors,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            market_snapshot=market,
        )
        self.store.save_advisor_brief(simulation.decision_id, brief)
        self.store.save_advisor_trace(simulation.decision_id, trace)
        self.event_bus.emit(
            "advisor_generated",
            {
                "scenario_id": scenario.scenario_id,
                "decision_id": simulation.decision_id,
                "fallback_used": fallback_used,
                "market_data_stale": market.stale,
                "quantitative_verdict": diagnostics.quantitative_verdict,
            },
        )
        if fallback_used:
            self.event_bus.emit(
                "advisor_fallback_used",
                {
                    "scenario_id": scenario.scenario_id,
                    "decision_id": simulation.decision_id,
                    "reason": fallback_reason,
                },
            )
        return brief
