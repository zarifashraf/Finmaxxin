from __future__ import annotations

from app.models.contracts import MarketSnapshot, ScenarioRecord, SimulationResult


class DeterministicFallbackAdvisor:
    def generate(self, scenario: ScenarioRecord, simulation: SimulationResult, market: MarketSnapshot) -> str:
        home = scenario.input.assumptions.home_purchase
        monthly_spend = scenario.snapshot.monthly_spend_cents
        emergency_target = monthly_spend * 6
        emergency_gap = max(0, emergency_target - scenario.snapshot.emergency_fund_cents)
        delta = simulation.delta_final_net_worth_cents
        beats_baseline = simulation.scenario_beats_baseline_probability

        verdict = "Wait"
        suggested_down_payment = "CAD $0 (insufficient home-price context)"
        primary_action = "Add a target home price and purchase month, then rerun the projection."

        if home is not None:
            price = home.price.amount_cents
            proposed_down = home.down_payment.amount_cents
            target_pct = 0.20
            if simulation.downside_p10_delta_cents < 0 or beats_baseline < 0.55:
                target_pct = 0.25
            if emergency_gap > 0:
                target_pct = max(target_pct, 0.30)

            recommended = int(price * target_pct)
            upper = int(price * min(target_pct + 0.05, 0.35))
            suggested_down_payment = f"CAD ${recommended / 100:,.0f} to CAD ${upper / 100:,.0f}"

            affordable_now = proposed_down >= recommended and emergency_gap == 0
            if delta > 0 and beats_baseline >= 0.6 and affordable_now:
                verdict = "Buy now"
                primary_action = (
                    f"Proceed only if you preserve at least CAD ${emergency_target / 100:,.0f} "
                    "as a six-month emergency buffer after closing."
                )
            else:
                verdict = "Wait"
                primary_action = (
                    f"Delay purchase by 6-12 months and raise liquid down payment toward {suggested_down_payment} "
                    "while preserving emergency reserves."
                )

        market_blurb = self._market_blurb(market)
        risks = self._risk_blurb(simulation, emergency_gap)
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
