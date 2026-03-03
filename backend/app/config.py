from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FINMAXXIN_", env_file=".env", extra="ignore")

    app_name: str = "Finmaxxin API"
    environment: str = "dev"
    model_version: str = "ml-ranker-v1"
    policy_version: str = "conservative-policy-v1"
    economic_assumptions_version: str = "ca-2026q1"
    monte_carlo_paths: int = Field(default=600, ge=100, le=5000)
    monte_carlo_seed: int = 42
    preview_ttl_minutes: int = 15
    required_bearer_token: str = "finmaxxin-demo-token"
    enable_advisor_brief: bool = True
    enable_market_fetch: bool = False
    market_refresh_days: int = Field(default=7, ge=1, le=30)
    llm_base_url: str = "http://llm:8080"
    llm_model_name: str = "qwen2.5-3b-instruct-q4_k_m.gguf"
    llm_timeout_ms: int = Field(default=20000, ge=1000, le=120000)
    llm_max_tokens: int = Field(default=320, ge=64, le=2048)
    llm_temperature: float = Field(default=0.2, ge=0.0, le=1.2)
    llm_regeneration_attempts: int = Field(default=1, ge=0, le=3)
    llm_max_response_chars: int = Field(default=4000, ge=500, le=12000)
    advisor_prompt_max_chars: int = Field(default=5000, ge=1000, le=20000)
    market_geo_scope: str = "CA"
    advisor_required_emergency_months: int = Field(default=6, ge=1, le=24)
    advisor_min_delta_buy_cents: int = Field(default=0, ge=-10_000_000_00, le=10_000_000_00)
    advisor_min_beats_baseline_probability: float = Field(default=0.6, ge=0.0, le=1.0)
    advisor_base_down_payment_pct: float = Field(default=0.20, ge=0.0, le=1.0)
    advisor_risk_down_payment_pct: float = Field(default=0.25, ge=0.0, le=1.0)
    advisor_emergency_down_payment_pct: float = Field(default=0.30, ge=0.0, le=1.0)
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"


settings = Settings()
