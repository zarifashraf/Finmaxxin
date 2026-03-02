from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock

import httpx

from app.config import Settings
from app.models.contracts import MarketSnapshot


class MarketDataService:
    """Fetches and caches free public market indicators for advisory context."""

    BOC_POLICY_RATE_URL = "https://www.bankofcanada.ca/valet/observations/V39079/json?recent=1"
    WORLDBANK_INFLATION_URL = "https://api.worldbank.org/v2/country/CAN/indicator/FP.CPI.TOTL.ZG?format=json&per_page=2"
    FRED_HOUSING_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=QCAR628BIS"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = Lock()
        self._cached_snapshot: MarketSnapshot | None = None

    def get_snapshot(self) -> MarketSnapshot:
        with self._lock:
            if self._cached_snapshot and self._is_fresh(self._cached_snapshot.fetched_at):
                return self._cached_snapshot

        if not self.settings.enable_market_fetch:
            snapshot = self._default_snapshot(stale=True, note="market_fetch_disabled")
            with self._lock:
                self._cached_snapshot = snapshot
            return snapshot

        fetched = self._fetch_snapshot()
        if fetched:
            with self._lock:
                self._cached_snapshot = fetched
            return fetched

        with self._lock:
            if self._cached_snapshot:
                stale = self._cached_snapshot.model_copy(
                    update={
                        "stale": True,
                        "source_notes": [*self._cached_snapshot.source_notes, "fetch_failed_using_cached_snapshot"],
                    }
                )
                self._cached_snapshot = stale
                return stale

        snapshot = self._default_snapshot(stale=True, note="fetch_failed_no_cache")
        with self._lock:
            self._cached_snapshot = snapshot
        return snapshot

    def _fetch_snapshot(self) -> MarketSnapshot | None:
        timeout = max(1.0, self.settings.llm_timeout_ms / 1000.0 / 4.0)
        policy = self._fetch_policy_rate(timeout)
        inflation = self._fetch_inflation(timeout)
        housing = self._fetch_housing_growth(timeout)

        if policy is None and inflation is None and housing is None:
            return None

        notes = []
        if policy is None:
            notes.append("policy_rate_missing")
        if inflation is None:
            notes.append("inflation_missing")
        if housing is None:
            notes.append("housing_growth_missing")

        return MarketSnapshot(
            geo_scope=self.settings.market_geo_scope,
            fetched_at=datetime.now(timezone.utc),
            policy_rate_pct=policy,
            inflation_yoy_pct=inflation,
            housing_growth_yoy_pct=housing,
            stale=False,
            source_urls=[self.BOC_POLICY_RATE_URL, self.WORLDBANK_INFLATION_URL, self.FRED_HOUSING_URL],
            source_notes=notes,
        )

    def _fetch_policy_rate(self, timeout_seconds: float) -> float | None:
        try:
            response = httpx.get(self.BOC_POLICY_RATE_URL, timeout=timeout_seconds)
            response.raise_for_status()
            payload = response.json()
            observations = payload.get("observations", [])
            if not observations:
                return None
            latest = observations[-1].get("V39079", {}).get("v")
            return float(latest) if latest is not None else None
        except Exception:
            return None

    def _fetch_inflation(self, timeout_seconds: float) -> float | None:
        try:
            response = httpx.get(self.WORLDBANK_INFLATION_URL, timeout=timeout_seconds)
            response.raise_for_status()
            payload = response.json()
            rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
            for row in rows:
                value = row.get("value")
                if value is not None:
                    return float(value)
            return None
        except Exception:
            return None

    def _fetch_housing_growth(self, timeout_seconds: float) -> float | None:
        """
        Computes approximate YoY growth from FRED CSV proxy:
        (latest - 4th previous) / previous * 100 for quarterly data.
        """
        try:
            response = httpx.get(self.FRED_HOUSING_URL, timeout=timeout_seconds)
            response.raise_for_status()
            lines = [line.strip() for line in response.text.splitlines() if line.strip()]
            values: list[float] = []
            for line in lines[1:]:
                parts = line.split(",")
                if len(parts) != 2:
                    continue
                raw = parts[1]
                if raw == ".":
                    continue
                try:
                    values.append(float(raw))
                except ValueError:
                    continue
            if len(values) < 5:
                return None
            latest = values[-1]
            prev_year = values[-5]
            if prev_year == 0:
                return None
            return ((latest - prev_year) / prev_year) * 100.0
        except Exception:
            return None

    def _is_fresh(self, fetched_at: datetime) -> bool:
        return datetime.now(timezone.utc) - fetched_at < timedelta(days=self.settings.market_refresh_days)

    def _default_snapshot(self, stale: bool, note: str) -> MarketSnapshot:
        return MarketSnapshot(
            geo_scope=self.settings.market_geo_scope,
            fetched_at=datetime.now(timezone.utc),
            policy_rate_pct=4.5,
            inflation_yoy_pct=2.8,
            housing_growth_yoy_pct=1.9,
            stale=stale,
            source_urls=[],
            source_notes=[note, "default_baseline_assumptions_used"],
        )
