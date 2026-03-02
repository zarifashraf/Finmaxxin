from datetime import datetime, timezone

from app.models.contracts import (
    AccountSnapshot,
    HomePurchaseAssumption,
    MarketSnapshot,
    Money,
    ScenarioAssumptions,
    ScenarioInput,
    ScenarioRecord,
    SimulationResult,
)
from app.services.advisory_validation import AdvisoryValidationService
from app.services.fallback_advisor import DeterministicFallbackAdvisor
from app.config import settings


def sample_scenario() -> ScenarioRecord:
    return ScenarioRecord(
        input=ScenarioInput(
            user_id="user-123",
            horizon_months=36,
            assumptions=ScenarioAssumptions(
                home_purchase=HomePurchaseAssumption(
                    price=Money(amount_cents=75000000),
                    down_payment=Money(amount_cents=12000000),
                    target_month=18,
                )
            ),
        ),
        snapshot=AccountSnapshot(
            user_id="user-123",
            assets_cents=18000000,
            liabilities_cents=3500000,
            monthly_income_cents=700000,
            monthly_spend_cents=420000,
            emergency_fund_cents=2000000,
            tfsa_room_cents=900000,
            rrsp_room_cents=1200000,
            fhsa_room_cents=450000,
            risk_profile="balanced",
            province="ON",
        ),
    )


def sample_simulation(scenario_id: str) -> SimulationResult:
    return SimulationResult(
        scenario_id=scenario_id,
        horizon_months=36,
        baseline_final_net_worth_cents=16500000,
        scenario_final_net_worth_cents=17100000,
        delta_final_net_worth_cents=600000,
        downside_p10_delta_cents=-200000,
        confidence=0.56,
        goal_success_probability=0.71,
        scenario_beats_baseline_probability=0.62,
        baseline_timeline={"p10_cents": [0], "p50_cents": [0], "p90_cents": [0]},
        timeline={"p10_cents": [0], "p50_cents": [0], "p90_cents": [0]},
        alternatives=[],
        economic_assumptions_version="test",
    )


def test_validation_rejects_missing_sections() -> None:
    validator = AdvisoryValidationService(settings)
    valid, errors = validator.validate("Verdict: Buy now")
    assert valid is False
    assert any(err.startswith("missing_section:") for err in errors)


def test_fallback_output_has_required_sections() -> None:
    advisor = DeterministicFallbackAdvisor()
    scenario = sample_scenario()
    simulation = sample_simulation(scenario.scenario_id)
    market = MarketSnapshot(
        geo_scope="CA",
        fetched_at=datetime.now(timezone.utc),
        policy_rate_pct=4.5,
        inflation_yoy_pct=2.7,
        housing_growth_yoy_pct=1.4,
        stale=False,
    )
    text = advisor.generate(scenario, simulation, market)
    assert "Verdict:" in text
    assert "Suggested down payment:" in text
    assert "Market conditions this week:" in text
    assert "Key risks:" in text
    assert "Primary action:" in text
    assert "Note:" in text
