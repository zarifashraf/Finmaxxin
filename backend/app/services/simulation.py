from __future__ import annotations

import hashlib

import numpy as np

from app.config import Settings
from app.models.contracts import (
    AccountSnapshot,
    PercentileSeries,
    ScenarioAssumptions,
    ScenarioInput,
    SimulationAlternative,
    SimulationResult,
)


class SimulationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, scenario_id: str, scenario_input: ScenarioInput, snapshot: AccountSnapshot) -> SimulationResult:
        base_assumptions = ScenarioAssumptions()
        baseline_paths = self._simulate_paths(scenario_id, snapshot, scenario_input.horizon_months, base_assumptions)
        scenario_paths = self._simulate_paths(
            scenario_id,
            snapshot,
            scenario_input.horizon_months,
            scenario_input.assumptions,
            salt="scenario",
        )

        baseline_final = baseline_paths[:, -1]
        scenario_final = scenario_paths[:, -1]
        deltas = scenario_final - baseline_final

        p10_delta = int(np.percentile(deltas, 10))
        median_delta = float(np.percentile(deltas, 50))
        probability_improves = float(np.mean(deltas > 0))
        directional_strength = abs(probability_improves - 0.5) * 2.0
        interquartile_spread = float(np.percentile(deltas, 75) - np.percentile(deltas, 25))
        signal_to_noise = abs(median_delta) / max(interquartile_spread, 1.0)
        stability = signal_to_noise / (1.0 + signal_to_noise)
        confidence = max(0.15, min(0.98, 0.2 + (0.55 * directional_strength) + (0.25 * stability)))
        initial_net_worth = snapshot.assets_cents - snapshot.liabilities_cents
        goal_success_probability = float(np.mean(scenario_final >= initial_net_worth))
        scenario_beats_baseline_probability = float(np.mean(deltas > 0))

        baseline_timeline = PercentileSeries(
            p10_cents=[int(v) for v in np.percentile(baseline_paths, 10, axis=0)],
            p50_cents=[int(v) for v in np.percentile(baseline_paths, 50, axis=0)],
            p90_cents=[int(v) for v in np.percentile(baseline_paths, 90, axis=0)],
        )
        timeline = PercentileSeries(
            p10_cents=[int(v) for v in np.percentile(scenario_paths, 10, axis=0)],
            p50_cents=[int(v) for v in np.percentile(scenario_paths, 50, axis=0)],
            p90_cents=[int(v) for v in np.percentile(scenario_paths, 90, axis=0)],
        )
        alternatives = [
            SimulationAlternative(
                name="downside_case",
                final_net_worth_cents=int(np.percentile(scenario_final, 10)),
                success_probability=float(np.mean(scenario_final >= initial_net_worth * 0.9)),
            ),
            SimulationAlternative(
                name="base_case",
                final_net_worth_cents=int(np.percentile(scenario_final, 50)),
                success_probability=goal_success_probability,
            ),
            SimulationAlternative(
                name="upside_case",
                final_net_worth_cents=int(np.percentile(scenario_final, 90)),
                success_probability=float(np.mean(scenario_final >= initial_net_worth * 1.1)),
            ),
        ]

        return SimulationResult(
            scenario_id=scenario_id,
            horizon_months=scenario_input.horizon_months,
            baseline_final_net_worth_cents=int(np.percentile(baseline_final, 50)),
            scenario_final_net_worth_cents=int(np.percentile(scenario_final, 50)),
            delta_final_net_worth_cents=int(np.percentile(scenario_final - baseline_final, 50)),
            downside_p10_delta_cents=p10_delta,
            confidence=confidence,
            goal_success_probability=goal_success_probability,
            scenario_beats_baseline_probability=scenario_beats_baseline_probability,
            baseline_timeline=baseline_timeline,
            timeline=timeline,
            alternatives=alternatives,
            economic_assumptions_version=self.settings.economic_assumptions_version,
        )

    def _simulate_paths(
        self,
        scenario_id: str,
        snapshot: AccountSnapshot,
        horizon_months: int,
        assumptions: ScenarioAssumptions,
        salt: str = "baseline",
    ) -> np.ndarray:
        seed = self._seed(scenario_id, salt)
        rng = np.random.default_rng(seed)
        paths = self.settings.monte_carlo_paths
        result = np.zeros((paths, horizon_months), dtype=np.int64)

        annual_return_mean = 0.048
        annual_return_std = 0.115
        monthly_mean = annual_return_mean / 12.0
        monthly_std = annual_return_std / np.sqrt(12.0)
        annual_home_return_mean = 0.02
        annual_home_return_std = 0.06
        monthly_home_mean = annual_home_return_mean / 12.0
        monthly_home_std = annual_home_return_std / np.sqrt(12.0)

        income_multiplier = 1.0 + ((assumptions.income_change_pct or 0.0) / 100.0)
        spend_multiplier = 1.0 + ((assumptions.monthly_spend_change_pct or 0.0) / 100.0)
        income = max(0, int(snapshot.monthly_income_cents * income_multiplier))
        spend = max(0, int(snapshot.monthly_spend_cents * spend_multiplier))
        extra_debt_payment = (
            assumptions.debt_plan.extra_payment_monthly.amount_cents if assumptions.debt_plan else 0
        )

        for p in range(paths):
            investable = snapshot.assets_cents
            liabilities = snapshot.liabilities_cents
            emergency_fund = snapshot.emergency_fund_cents
            home_value = 0
            home_purchase_done = False

            for month in range(1, horizon_months + 1):
                monthly_return = float(rng.normal(monthly_mean, monthly_std))
                investable = int(investable * (1.0 + monthly_return))
                if home_purchase_done and home_value > 0:
                    home_return = float(rng.normal(monthly_home_mean, monthly_home_std))
                    home_value = int(home_value * (1.0 + home_return))

                net_cash_flow = income - spend

                if extra_debt_payment > 0 and liabilities > 0:
                    debt_payment = min(extra_debt_payment, liabilities)
                    liabilities -= debt_payment
                    net_cash_flow -= debt_payment

                if assumptions.home_purchase and not home_purchase_done and month == assumptions.home_purchase.target_month:
                    price = assumptions.home_purchase.price.amount_cents
                    down = assumptions.home_purchase.down_payment.amount_cents
                    mortgage = max(0, price - down)
                    investable -= down
                    liabilities += mortgage
                    home_value += price
                    home_purchase_done = True

                if net_cash_flow >= 0:
                    emergency_share = int(net_cash_flow * 0.25)
                    invest_share = net_cash_flow - emergency_share
                    emergency_fund += emergency_share
                    investable += invest_share
                else:
                    deficit = abs(net_cash_flow)
                    draw_from_emergency = min(deficit, emergency_fund)
                    emergency_fund -= draw_from_emergency
                    remaining = deficit - draw_from_emergency
                    investable -= remaining

                net_worth = investable + emergency_fund + home_value - liabilities
                result[p, month - 1] = net_worth

        return result

    def _seed(self, scenario_id: str, salt: str) -> int:
        seed_material = f"{self.settings.monte_carlo_seed}:{scenario_id}:{salt}".encode("utf-8")
        hashed = int(hashlib.sha256(seed_material).hexdigest(), 16)
        return hashed % (2**32 - 1)
