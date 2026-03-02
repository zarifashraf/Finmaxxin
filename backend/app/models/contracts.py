from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class Currency(str, Enum):
    CAD = "CAD"


class Money(BaseModel):
    amount_cents: int = Field(..., description="Amount in cents")
    currency: Currency = Currency.CAD


class HomePurchaseAssumption(BaseModel):
    price: Money
    down_payment: Money
    target_month: int = Field(..., ge=1, le=60)

    @model_validator(mode="after")
    def validate_down_payment(self) -> "HomePurchaseAssumption":
        if self.down_payment.amount_cents > self.price.amount_cents:
            raise ValueError("down_payment cannot exceed price")
        return self


class DebtPlanAssumption(BaseModel):
    extra_payment_monthly: Money


class ScenarioAssumptions(BaseModel):
    income_change_pct: float | None = Field(default=None, ge=-100.0, le=200.0)
    monthly_spend_change_pct: float | None = Field(default=None, ge=-80.0, le=200.0)
    home_purchase: HomePurchaseAssumption | None = None
    debt_plan: DebtPlanAssumption | None = None


class ScenarioInput(BaseModel):
    user_id: str
    horizon_months: int = Field(default=60, ge=1, le=60)
    assumptions: ScenarioAssumptions = Field(default_factory=ScenarioAssumptions)

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("user_id cannot be empty")
        return cleaned


class AccountSnapshot(BaseModel):
    user_id: str
    assets_cents: int = Field(..., ge=0)
    liabilities_cents: int = Field(..., ge=0)
    monthly_income_cents: int = Field(..., ge=0)
    monthly_spend_cents: int = Field(..., ge=0)
    emergency_fund_cents: int = Field(..., ge=0)
    tfsa_room_cents: int = Field(..., ge=0)
    rrsp_room_cents: int = Field(..., ge=0)
    fhsa_room_cents: int = Field(..., ge=0)
    risk_profile: str = Field(default="balanced")
    province: str = Field(default="ON")


class ScenarioRecord(BaseModel):
    scenario_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    input: ScenarioInput
    snapshot: AccountSnapshot


class PercentileSeries(BaseModel):
    p10_cents: list[int]
    p50_cents: list[int]
    p90_cents: list[int]


class SimulationAlternative(BaseModel):
    name: str
    final_net_worth_cents: int
    success_probability: float = Field(..., ge=0.0, le=1.0)


class SimulationResult(BaseModel):
    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    scenario_id: str
    horizon_months: int
    baseline_final_net_worth_cents: int
    scenario_final_net_worth_cents: int
    delta_final_net_worth_cents: int
    downside_p10_delta_cents: int
    confidence: float = Field(..., ge=0.0, le=1.0)
    goal_success_probability: float = Field(..., ge=0.0, le=1.0)
    scenario_beats_baseline_probability: float = Field(..., ge=0.0, le=1.0)
    baseline_timeline: PercentileSeries
    timeline: PercentileSeries
    alternatives: list[SimulationAlternative]
    economic_assumptions_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskLevel(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


class Recommendation(BaseModel):
    recommendation_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    expected_net_worth_delta: Money
    downside_p10_delta: Money
    goal_success_probability: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: list[str]
    key_assumptions: list[str]
    sensitivity_top_factors: list[str]
    risk_level: RiskLevel
    score: float = Field(..., ge=0.0, le=1.0)
    action_type: str


class ScenarioCreateResponse(BaseModel):
    scenario_id: str
    created_at: datetime
    snapshot: AccountSnapshot


class RecommendationListResponse(BaseModel):
    scenario_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    recommendations: list[Recommendation]


class ActionPreviewRequest(BaseModel):
    scenario_id: str
    recommendation_id: str
    action_type: str


class ExecutionPreview(BaseModel):
    preview_id: str = Field(default_factory=lambda: str(uuid4()))
    action_id: str
    requires_confirmation: bool = True
    projected_impact_12m: Money
    fees: Money
    warnings: list[str]
    expires_at: datetime


class ActionExecuteRequest(BaseModel):
    preview_id: str
    action_id: str
    confirm: bool = True
    idempotency_key: str

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 8:
            raise ValueError("idempotency_key must be at least 8 chars")
        return cleaned


class ActionExecutionResult(BaseModel):
    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    action_id: str
    status: str
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    idempotency_key: str
    upstream_reference: str


class DecisionTrace(BaseModel):
    decision_id: str
    scenario_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_version: str
    policy_version: str
    economic_assumptions_version: str
    input_snapshot_hash: str
    feature_contributions: dict[str, float]
    policy_checks: list[dict[str, Any]]
    simulation_seed: int
    assumptions: dict[str, Any]


class EventRecord(BaseModel):
    event_name: str
    payload: dict[str, Any]
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
