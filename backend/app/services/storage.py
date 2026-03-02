from __future__ import annotations

from threading import Lock

from app.models.contracts import (
    ActionExecutionResult,
    AdvisorBriefResponse,
    AdvisorBriefTrace,
    DecisionTrace,
    EventRecord,
    ExecutionPreview,
    Recommendation,
    ScenarioRecord,
    SimulationResult,
)


class InMemoryStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self.scenarios: dict[str, ScenarioRecord] = {}
        self.simulations: dict[str, SimulationResult] = {}
        self.recommendations: dict[str, list[Recommendation]] = {}
        self.previews: dict[str, ExecutionPreview] = {}
        self.executions_by_idempotency: dict[str, ActionExecutionResult] = {}
        self.decision_traces: dict[str, DecisionTrace] = {}
        self.advisor_briefs: dict[str, AdvisorBriefResponse] = {}
        self.advisor_traces: dict[str, AdvisorBriefTrace] = {}
        self.events: list[EventRecord] = []

    def save_scenario(self, scenario: ScenarioRecord) -> None:
        with self._lock:
            self.scenarios[scenario.scenario_id] = scenario

    def get_scenario(self, scenario_id: str) -> ScenarioRecord | None:
        return self.scenarios.get(scenario_id)

    def save_simulation(self, simulation: SimulationResult) -> None:
        with self._lock:
            self.simulations[simulation.scenario_id] = simulation

    def get_simulation(self, scenario_id: str) -> SimulationResult | None:
        return self.simulations.get(scenario_id)

    def save_recommendations(self, scenario_id: str, recs: list[Recommendation]) -> None:
        with self._lock:
            self.recommendations[scenario_id] = recs

    def get_recommendations(self, scenario_id: str) -> list[Recommendation]:
        return self.recommendations.get(scenario_id, [])

    def save_preview(self, preview: ExecutionPreview) -> None:
        with self._lock:
            self.previews[preview.preview_id] = preview

    def get_preview(self, preview_id: str) -> ExecutionPreview | None:
        return self.previews.get(preview_id)

    def save_execution(self, idempotency_key: str, result: ActionExecutionResult) -> None:
        with self._lock:
            self.executions_by_idempotency[idempotency_key] = result

    def get_execution_by_idempotency(self, idempotency_key: str) -> ActionExecutionResult | None:
        return self.executions_by_idempotency.get(idempotency_key)

    def save_trace(self, trace: DecisionTrace) -> None:
        with self._lock:
            self.decision_traces[trace.decision_id] = trace

    def get_trace(self, decision_id: str) -> DecisionTrace | None:
        return self.decision_traces.get(decision_id)

    def save_advisor_brief(self, decision_id: str, brief: AdvisorBriefResponse) -> None:
        with self._lock:
            self.advisor_briefs[decision_id] = brief

    def get_advisor_brief(self, decision_id: str) -> AdvisorBriefResponse | None:
        return self.advisor_briefs.get(decision_id)

    def save_advisor_trace(self, decision_id: str, trace: AdvisorBriefTrace) -> None:
        with self._lock:
            self.advisor_traces[decision_id] = trace

    def get_advisor_trace(self, decision_id: str) -> AdvisorBriefTrace | None:
        return self.advisor_traces.get(decision_id)

    def append_event(self, event: EventRecord) -> None:
        with self._lock:
            self.events.append(event)
