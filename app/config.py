import os
from functools import lru_cache
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field


class Settings(BaseModel):
    data_provider: str = Field(default="mock", validation_alias="DATA_PROVIDER")
    market_provider: str = Field(default="mock", validation_alias="MARKET_PROVIDER")
    database_path: str = Field(default="/data/trader_assistant.db", validation_alias="DATABASE_PATH")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    ai_enabled: bool = Field(default=False, validation_alias="AI_ENABLED")
    always_in_session: bool = Field(default=False, validation_alias="ALWAYS_IN_SESSION")
    symbol_default: str = Field(default="XAUUSD", validation_alias="SYMBOL_DEFAULT")
    tf_signal: str = Field(default="M15", validation_alias="TF_SIGNAL")
    tf_context: str = Field(default="H1", validation_alias="TF_CONTEXT")
    spread_max: float = Field(default=20.0, validation_alias="SPREAD_MAX")
    hard_spread_max_points: float = Field(default=40.0, validation_alias="HARD_SPREAD_MAX_POINTS")
    soft_spread_start_points: float = Field(default=20.0, validation_alias="SOFT_SPREAD_START_POINTS")
    soft_spread_max_penalty: int = Field(default=30, validation_alias="SOFT_SPREAD_MAX_PENALTY")
    hard_spread_max_ratio: float = Field(default=0.12, validation_alias="HARD_SPREAD_MAX_RATIO")
    soft_spread_start_ratio: float = Field(default=0.06, validation_alias="SOFT_SPREAD_START_RATIO")
    atr_max: float = Field(default=2.0, validation_alias="ATR_MAX")
    sl_max_atr_multiple: float = Field(default=1.5, validation_alias="SL_MAX_ATR_MULTIPLE")
    sl_max_points: float = Field(default=25.0, validation_alias="SL_MAX_POINTS")
    rr_min: float = Field(default=2.0, validation_alias="RR_MIN")
    cooldown_minutes: int = Field(default=20, validation_alias="COOLDOWN_MINUTES")
    daily_budget_amount: float = Field(default=20.0, validation_alias="DAILY_BUDGET_AMOUNT")
    news_calendar_path: str = Field(
        default="data/news_calendar_mock.json", validation_alias="NEWS_CALENDAR_PATH"
    )
    news_lock_minutes: int = Field(
        default=30, validation_alias=AliasChoices("NEWS_LOCK_MIN", "NEWS_LOCK_MINUTES")
    )
    news_provider: str = Field(default="mock", validation_alias="NEWS_PROVIDER")
    news_api_base_url: str = Field(default="", validation_alias="NEWS_API_BASE_URL")
    news_api_key: str = Field(default="", validation_alias="NEWS_API_KEY")
    te_base_url: str = Field(default="https://api.tradingeconomics.com", validation_alias="TE_BASE_URL")
    te_api_key: str = Field(default="", validation_alias="TE_API_KEY")
    news_cache_ttl_sec: int = Field(default=300, validation_alias="NEWS_CACHE_TTL_SEC")
    news_timeout_sec: int = Field(default=4, validation_alias="NEWS_TIMEOUT_SEC")
    news_retry: int = Field(default=1, validation_alias="NEWS_RETRY")
    news_fallback_to_mock: bool = Field(default=True, validation_alias="NEWS_FALLBACK_TO_MOCK")
    news_calendar_currencies: str = Field(default="USD", validation_alias="NEWS_CALENDAR_CURRENCIES")
    news_calendar_impact_min: str = Field(default="HIGH", validation_alias="NEWS_CALENDAR_IMPACT_MIN")
    news_countries: str = Field(default="united states", validation_alias="NEWS_COUNTRIES")
    news_importance_min: int = Field(default=2, validation_alias="NEWS_IMPORTANCE_MIN")
    news_lookahead_hours: int = Field(default=24, validation_alias="NEWS_LOOKAHEAD_HOURS")
    news_prealert_minutes: str = Field(default="60,30,15", validation_alias="NEWS_PREALERT_MINUTES")
    news_lock_high_pre_min: int = Field(
        default=30,
        validation_alias=AliasChoices("NEWS_LOCK_HIGH_PRE_MIN", "NEWS_HIGH_PRE_MIN"),
    )
    news_lock_high_post_min: int = Field(
        default=90,
        validation_alias=AliasChoices("NEWS_LOCK_HIGH_POST_MIN", "NEWS_HIGH_POST_MIN"),
    )
    news_lock_med_pre_min: int = Field(default=10, validation_alias="NEWS_LOCK_MED_PRE_MIN")
    news_lock_med_post_min: int = Field(default=5, validation_alias="NEWS_LOCK_MED_POST_MIN")
    context_enabled: bool = Field(default=False, validation_alias="CONTEXT_ENABLED")
    context_api_base_url: str = Field(default="", validation_alias="CONTEXT_API_BASE_URL")
    context_api_key: str = Field(default="", validation_alias="CONTEXT_API_KEY")
    mt5_bridge_url: str = Field(default="", validation_alias="MT5_BRIDGE_URL")
    data_max_age_sec: int = Field(default=120, validation_alias="DATA_MAX_AGE_SEC")
    trading_session_mode: str = Field(default="windows", validation_alias="TRADING_SESSION_MODE")
    market_close_start: str = Field(default="23:55", validation_alias="MARKET_CLOSE_START")
    market_close_end: str = Field(default="00:05", validation_alias="MARKET_CLOSE_END")
    telegram_enabled: bool = Field(default=False, validation_alias="TELEGRAM_ENABLED")
    telegram_bot_token: str = Field(default="", validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", validation_alias="TELEGRAM_CHAT_ID")
    telegram_send_no_go_important: bool = Field(
        default=False, validation_alias="TELEGRAM_SEND_NO_GO_IMPORTANT"
    )
    telegram_no_go_important_blocks: str = Field(
        default="NEWS_LOCK,DATA_OFF,DAILY_BUDGET_REACHED",
        validation_alias="TELEGRAM_NO_GO_IMPORTANT_BLOCKS",
    )
    admin_token: str = Field(default="", validation_alias="ADMIN_TOKEN")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    ai_model: str = Field(default="gpt-4o-mini", validation_alias=AliasChoices("AI_MODEL", "OPENAI_MODEL"))
    ai_timeout_sec: int = Field(default=6, validation_alias="AI_TIMEOUT_SEC")
    ai_price_input_per_1m: float = Field(default=0.15, validation_alias="AI_PRICE_INPUT_PER_1M")
    ai_price_output_per_1m: float = Field(default=0.60, validation_alias="AI_PRICE_OUTPUT_PER_1M")
    ai_max_cost_eur_per_day: float = Field(default=1.0, validation_alias="AI_MAX_COST_EUR_PER_DAY")
    ai_max_tokens_per_message: int = Field(default=800, validation_alias="AI_MAX_TOKENS_PER_MESSAGE")
    coach_language: str = Field(default="fr", validation_alias="COACH_LANGUAGE")
    coach_mode: str = Field(default="pro", validation_alias="COACH_MODE")
    fx_eurusd: float = Field(default=1.08, validation_alias="FX_EURUSD")

    # Outcome agent
    outcome_agent_enabled: bool = Field(default=False, validation_alias="OUTCOME_AGENT_ENABLED")
    outcome_agent_interval_sec: int = Field(default=300, validation_alias="OUTCOME_AGENT_INTERVAL_SEC")
    outcome_agent_lookback_hours: int = Field(default=24, validation_alias="OUTCOME_AGENT_LOOKBACK_HOURS")
    outcome_agent_wait_minutes: int = Field(default=10, validation_alias="OUTCOME_AGENT_WAIT_MINUTES")
    outcome_agent_min_age_hours: int = Field(default=24, validation_alias="OUTCOME_AGENT_MIN_AGE_HOURS")
    outcome_agent_run_only_during_market_close: bool = Field(
        default=True, validation_alias="OUTCOME_AGENT_RUN_ONLY_DURING_MARKET_CLOSE"
    )
    outcome_agent_horizon_minutes: int = Field(default=180, validation_alias="OUTCOME_AGENT_HORIZON_MINUTES")
    outcome_agent_candle_tf: str = Field(default="M1", validation_alias="OUTCOME_AGENT_CANDLE_TF")
    outcome_agent_max_per_loop: int = Field(default=20, validation_alias="OUTCOME_AGENT_MAX_PER_LOOP")

    def model_post_init(self, __context: Optional[dict]) -> None:  # type: ignore[override]
        self.data_provider = str(self.data_provider).lower()
        self.market_provider = str(self.market_provider).lower()
        self.log_level = str(self.log_level).upper()
        self.news_provider = str(self.news_provider).lower()
        self.trading_session_mode = str(self.trading_session_mode).lower()


@lru_cache
def get_settings() -> Settings:
    values = {k: v for k, v in os.environ.items()}
    return Settings(**values)
