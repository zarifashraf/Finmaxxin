from __future__ import annotations

import hashlib
import json

from app.config import Settings
from app.models.contracts import DecisionTrace, ScenarioRecord, SimulationResult


class TransparencyService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_trace(
        self,
        scenario: ScenarioRecord,
        simulation: SimulationResult,
        feature_contributions: dict[str, float],
        policy_checks: list[dict],
    ) -> DecisionTrace:
        input_payload = scenario.model_dump(mode="json")
        input_hash = hashlib.sha256(json.dumps(input_payload, sort_keys=True).encode("utf-8")).hexdigest()
        return DecisionTrace(
            decision_id=simulation.decision_id,
            scenario_id=scenario.scenario_id,
            model_version=self.settings.model_version,
            policy_version=self.settings.policy_version,
            economic_assumptions_version=self.settings.economic_assumptions_version,
            input_snapshot_hash=input_hash,
            feature_contributions=feature_contributions,
            policy_checks=policy_checks,
            simulation_seed=self.settings.monte_carlo_seed,
            assumptions=scenario.input.assumptions.model_dump(mode="json"),
        )
