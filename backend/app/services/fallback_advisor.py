from __future__ import annotations

from app.config import Settings
from app.models.contracts import AdvisorDiagnostics, DecisionGate, MarketSnapshot, ScenarioRecord, SimulationResult


class DeterministicFallbackAdvisor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate(self, scenario: ScenarioRecord, simulation: SimulationResult) -> AdvisorDiagnostics:
        home = scenario.input.assumptions.home_purchase
        monthly_spend = scenario.snapshot.monthly_spend_cents
        emergency_target = monthly_spend * self.settings.advisor_required_emergency_months
        emergency_gap = max(0, emergency_target - scenario.snapshot.emergency_fund_cents)

        if home is None:
            return AdvisorDiagnostics(
                quantitative_verdict="wait",
                wait_reasons=["missing_home_inputs"],
                gates=[
                    DecisionGate(
                        gate_id="home_inputs_present",
                        label="Home price, down payment, and target month provided",
                        passed=False,
                        observed="not provided",
                        required="required to evaluate buy-vs-wait",
                    )
                ],
                emergency_fund_target_cents=emergency_target,
                emergency_fund_gap_cents=emergency_gap,
            )

        price = home.price.amount_cents
        proposed_down = home.down_payment.amount_cents
        delta = simulation.delta_final_net_worth_cents
        beats_baseline = simulation.scenario_beats_baseline_probability

        target_pct = self.settings.advisor_base_down_payment_pct
        if simulation.downside_p10_delta_cents < 0 or beats_baseline < 0.55:
            target_pct = max(target_pct, self.settings.advisor_risk_down_payment_pct)
        if emergency_gap > 0:
            target_pct = max(target_pct, self.settings.advisor_emergency_down_payment_pct)

        recommended = int(price * target_pct)
        upper = int(price * min(target_pct + 0.05, 0.35))

        delta_gate = delta >= self.settings.advisor_min_delta_buy_cents
        probability_gate = beats_baseline >= self.settings.advisor_min_beats_baseline_probability
        down_payment_gate = proposed_down >= recommended
        emergency_gate = emergency_gap == 0
        liquid_funding_gate = scenario.snapshot.assets_cents >= proposed_down

        gates = [
            DecisionGate(
                gate_id="delta_threshold",
                label="Scenario net-worth delta gate",
                passed=delta_gate,
                observed=f"{delta / 100:,.0f} CAD",
                required=f">= {self.settings.advisor_min_delta_buy_cents / 100:,.0f} CAD",
            ),
            DecisionGate(
                gate_id="beats_baseline_probability",
                label="Scenario beats baseline probability",
                passed=probability_gate,
                observed=f"{beats_baseline * 100:.1f}%",
                required=f">= {self.settings.advisor_min_beats_baseline_probability * 100:.1f}%",
            ),
            DecisionGate(
                gate_id="down_payment_target",
                label="Down payment target",
                passed=down_payment_gate,
                observed=f"{proposed_down / 100:,.0f} CAD",
                required=f">= {recommended / 100:,.0f} CAD",
            ),
            DecisionGate(
                gate_id="emergency_fund",
                label=f"Emergency reserve ({self.settings.advisor_required_emergency_months} months)",
                passed=emergency_gate,
                observed=f"gap {emergency_gap / 100:,.0f} CAD",
                required="gap 0 CAD",
            ),
            DecisionGate(
                gate_id="liquid_funding",
                label="Down payment funded by liquid assets",
                passed=liquid_funding_gate,
                observed=f"{scenario.snapshot.assets_cents / 100:,.0f} CAD assets",
                required=f">= {proposed_down / 100:,.0f} CAD",
            ),
        ]

        wait_reasons: list[str] = []
        if not delta_gate:
            wait_reasons.append("scenario_underperforms_threshold")
        if not probability_gate:
            wait_reasons.append("scenario_probability_below_threshold")
        if not down_payment_gate:
            wait_reasons.append("down_payment_below_recommended_range")
        if not emergency_gate:
            wait_reasons.append("emergency_fund_gap")
        if not liquid_funding_gate:
            wait_reasons.append("insufficient_liquid_assets_for_down_payment")

        verdict = "buy_now" if not wait_reasons else "wait"
        return AdvisorDiagnostics(
            quantitative_verdict=verdict,
            wait_reasons=wait_reasons,
            gates=gates,
            recommended_down_payment_cents=recommended,
            recommended_down_payment_upper_cents=upper,
            emergency_fund_target_cents=emergency_target,
            emergency_fund_gap_cents=emergency_gap,
        )

    def generate(
        self,
        scenario: ScenarioRecord,
        simulation: SimulationResult,
        market: MarketSnapshot,
        diagnostics: AdvisorDiagnostics | None = None,
    ) -> str:
        diag = diagnostics or self.evaluate(scenario, simulation)
        verdict = "Buy now" if diag.quantitative_verdict == "buy_now" else "Wait"
        suggested_down_payment = self._format_down_payment(diag)

        if diag.quantitative_verdict == "buy_now":
            emergency_target = diag.emergency_fund_target_cents or 0
            primary_action = (
                f"Proceed only if you preserve at least CAD ${emergency_target / 100:,.0f} "
                f"as a {self.settings.advisor_required_emergency_months}-month emergency buffer after closing."
            )
        elif "missing_home_inputs" in diag.wait_reasons:
            primary_action = "Add a target home price and purchase month, then rerun the projection."
        else:
            primary_action = (
                f"Delay purchase by 6-12 months and raise liquid down payment toward {suggested_down_payment} "
                "while preserving emergency reserves."
            )

        market_blurb = self._market_blurb(market)
        risks = self._risk_blurb(simulation, diag.emergency_fund_gap_cents or 0)
        note = (
            "This is an educational planning estimate based on scenario assumptions and public market indicators, "
            "not individualized investment advice."
        )
        return (
            f"Verdict: {verdict}\n"
            f"Suggested down payment: {suggested_down_payment}. This range balances affordability and downside protection.\n"
            f"Market conditions this week: {market_blurb}\n"
            f"Key risks: {risks}\n"
            f"Primary action: {primary_action}\n"
            f"Note: {note}\n"
        )

    def _format_down_payment(self, diagnostics: AdvisorDiagnostics) -> str:
        recommended = diagnostics.recommended_down_payment_cents
        upper = diagnostics.recommended_down_payment_upper_cents
        if recommended is None:
            return "CAD $0 (insufficient home-price context)"
        if upper is None or upper <= recommended:
            return f"CAD ${recommended / 100:,.0f}"
        return f"CAD ${recommended / 100:,.0f} to CAD ${upper / 100:,.0f}"

    def _market_blurb(self, market: MarketSnapshot) -> str:
        policy = "unknown" if market.policy_rate_pct is None else f"{market.policy_rate_pct:.2f}% policy-rate environment"
        inflation = "unknown" if market.inflation_yoy_pct is None else f"{market.inflation_yoy_pct:.2f}% inflation"
        housing = (
            "unknown"
            if market.housing_growth_yoy_pct is None
            else f"{market.housing_growth_yoy_pct:.2f}% YoY housing-index proxy change"
        )
        stale = " Data is stale; interpret with caution." if market.stale else ""
        return f"Canada-wide baseline currently reflects {policy}, {inflation}, and {housing}.{stale}"

    def _risk_blurb(self, simulation: SimulationResult, emergency_gap_cents: int) -> str:
        items = []
        if simulation.downside_p10_delta_cents < 0:
            items.append(
                f"stress outcomes include around CAD ${abs(simulation.downside_p10_delta_cents) / 100:,.0f} downside versus baseline"
            )
        if simulation.scenario_beats_baseline_probability < 0.5:
            items.append("your scenario currently loses to baseline in most simulations")
        if emergency_gap_cents > 0:
            items.append(f"emergency reserve shortfall of about CAD ${emergency_gap_cents / 100:,.0f}")
        if not items:
            items.append("market volatility and interest-rate path uncertainty remain")
        return "; ".join(items) + "."
