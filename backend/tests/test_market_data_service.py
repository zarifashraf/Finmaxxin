from app.config import Settings
from app.services.market_data import MarketDataService


def test_market_snapshot_returns_default_when_fetch_disabled() -> None:
    local_settings = Settings(enable_market_fetch=False, market_geo_scope="CA")
    service = MarketDataService(local_settings)
    snapshot = service.get_snapshot()
    assert snapshot.geo_scope == "CA"
    assert snapshot.stale is True
    assert snapshot.policy_rate_pct is not None
    assert "default_baseline_assumptions_used" in snapshot.source_notes
