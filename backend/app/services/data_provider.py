from __future__ import annotations

import hashlib

from app.models.contracts import AccountSnapshot, SnapshotOverrides


class AccountDataProvider:
    """
    Prototype adapter with optional user-provided snapshot overrides.
    If overrides are not provided, a deterministic synthetic baseline is used.
    """

    @staticmethod
    def get_account_snapshot(user_id: str, overrides: SnapshotOverrides | None = None) -> AccountSnapshot:
        base = AccountDataProvider._synthetic_snapshot(user_id)
        if overrides is None:
            return base

        assets_cents = base.assets_cents
        monthly_income_cents = base.monthly_income_cents
        monthly_spend_cents = base.monthly_spend_cents
        emergency_fund_cents = base.emergency_fund_cents
        liabilities_cents = 0

        if overrides.liquid_assets_cents is not None:
            assets_cents = overrides.liquid_assets_cents
        if overrides.annual_income_cents is not None:
            monthly_income_cents = int(round(overrides.annual_income_cents / 12.0))
        if overrides.monthly_spend_cents is not None:
            monthly_spend_cents = overrides.monthly_spend_cents
        elif overrides.annual_income_cents is not None:
            monthly_spend_cents = int(round(monthly_income_cents * 0.60))
        if overrides.emergency_fund_cents is not None:
            emergency_fund_cents = min(overrides.emergency_fund_cents, assets_cents)
        elif overrides.liquid_assets_cents is not None or overrides.annual_income_cents is not None:
            emergency_fund_cents = min(assets_cents, int(monthly_spend_cents * 3))

        return AccountSnapshot(
            user_id=user_id,
            assets_cents=max(0, assets_cents),
            liabilities_cents=max(0, liabilities_cents),
            monthly_income_cents=max(0, monthly_income_cents),
            monthly_spend_cents=max(0, monthly_spend_cents),
            emergency_fund_cents=max(0, emergency_fund_cents),
            tfsa_room_cents=base.tfsa_room_cents,
            rrsp_room_cents=base.rrsp_room_cents,
            fhsa_room_cents=base.fhsa_room_cents,
            risk_profile=base.risk_profile,
            province=base.province,
        )

    @staticmethod
    def _synthetic_snapshot(user_id: str) -> AccountSnapshot:
        hashed = int(hashlib.sha256(user_id.encode("utf-8")).hexdigest(), 16)
        assets = 2_500_000 + (hashed % 15_000_000)
        liabilities = 500_000 + (hashed % 2_000_000)
        income = 450_000 + (hashed % 350_000)
        spend = 250_000 + (hashed % 250_000)
        emergency = min(assets // 4, 2_000_000 + (hashed % 1_000_000))
        tfsa = 500_000 + (hashed % 1_500_000)
        rrsp = 900_000 + (hashed % 2_500_000)
        fhsa = 200_000 + (hashed % 600_000)
        risk = ["conservative", "balanced", "growth"][hashed % 3]
        province = ["ON", "QC", "BC", "AB"][hashed % 4]
        return AccountSnapshot(
            user_id=user_id,
            assets_cents=assets,
            liabilities_cents=liabilities,
            monthly_income_cents=income,
            monthly_spend_cents=spend,
            emergency_fund_cents=emergency,
            tfsa_room_cents=tfsa,
            rrsp_room_cents=rrsp,
            fhsa_room_cents=fhsa,
            risk_profile=risk,
            province=province,
        )
