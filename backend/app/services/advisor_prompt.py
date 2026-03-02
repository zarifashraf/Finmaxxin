from __future__ import annotations

import json
import re

from app.config import Settings
from app.models.contracts import MarketSnapshot, ScenarioRecord, SimulationResult


class AdvisorPromptService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build(self, scenario: ScenarioRecord, simulation: SimulationResult, market: MarketSnapshot) -> tuple[str, str]:
        system_prompt = (
            "You are a cautious financial planning assistant. "
            "Use only the facts in the prompt. Do not invent missing data. "
            "Return exactly these labeled sections in plain text:\n"
            "Verdict:\n"
            "Suggested down payment:\n"
            "Market conditions this week:\n"
            "Key risks:\n"
            "Primary action:\n"
            "Note:\n"
            "Down payment must include an explicit CAD amount or CAD range."
        )

        context = {
            "user_profile": {
                "province": scenario.snapshot.province,
                "risk_profile": scenario.snapshot.risk_profile,
                "assets_cents": scenario.snapshot.assets_cents,
                "liabilities_cents": scenario.snapshot.liabilities_cents,
                "monthly_income_cents": scenario.snapshot.monthly_income_cents,
                "monthly_spend_cents": scenario.snapshot.monthly_spend_cents,
                "emergency_fund_cents": scenario.snapshot.emergency_fund_cents,
            },
            "scenario_assumptions": scenario.input.assumptions.model_dump(mode="json"),
            "simulation": {
                "horizon_months": simulation.horizon_months,
                "baseline_final_net_worth_cents": simulation.baseline_final_net_worth_cents,
                "scenario_final_net_worth_cents": simulation.scenario_final_net_worth_cents,
                "delta_final_net_worth_cents": simulation.delta_final_net_worth_cents,
                "downside_p10_delta_cents": simulation.downside_p10_delta_cents,
                "confidence": simulation.confidence,
                "scenario_beats_baseline_probability": simulation.scenario_beats_baseline_probability,
            },
            "market_snapshot": market.model_dump(mode="json"),
            "policy": {
                "risk_posture": "conservative",
                "primary_action_policy": "exactly_one_primary_action",
            },
        }

        serialized = self._sanitize_and_clip(json.dumps(context, separators=(",", ":"), ensure_ascii=True))
        user_prompt = (
            "Generate a one-action financial advisory brief focused on home-buy decision quality.\n"
            "Use the provided context only.\n"
            "Context JSON:\n"
            f"{serialized}\n"
            "Finish response with token <END_OF_ADVICE>."
        )
        return system_prompt, user_prompt

    def build_repair_prompt(self, prior_response: str, validation_errors: list[str]) -> str:
        clipped_prior = self._sanitize_and_clip(prior_response)
        errors = ", ".join(validation_errors)
        return (
            "Your previous response failed validation.\n"
            f"Issues: {errors}\n"
            "Rewrite fully and include all required labeled sections with valid CAD down payment guidance.\n"
            f"Previous invalid response:\n{clipped_prior}\n"
            "Finish response with token <END_OF_ADVICE>."
        )

    def _sanitize_and_clip(self, text: str) -> str:
        sanitized = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", text)
        max_chars = self.settings.advisor_prompt_max_chars
        if len(sanitized) > max_chars:
            return sanitized[:max_chars]
        return sanitized
