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
    hard_spread_max_pts: float = Field(default=30.0, validation_alias="HARD_SPREAD_MAX_PTS")
    soft_spread_start_pts: float = Field(default=18.0, validation_alias="SOFT_SPREAD_START_PTS")
    hard_spread_max_ratio: float = Field(default=0.15, validation_alias="HARD_SPREAD_MAX_RATIO")
    atr_max: float = Field(default=2.0, validation_alias="ATR_MAX")
    rr_min: float = Field(default=1.5, validation_alias="RR_MIN")
    rr_min_tp1: float = Field(default=0.4, validation_alias="RR_MIN_TP1")
    rr_hard_min_tp1: float = Field(default=0.15, validation_alias="RR_HARD_MIN_TP1")  # scalp: sécurité extrême uniquement, RR ne bloque plus sinon
    sl_min_pts: float = Field(default=20.0, validation_alias="SL_MIN_PTS")
    sl_max_pts: float = Field(default=25.0, validation_alias="SL_MAX_PTS")
    tp1_min_pts: float = Field(default=7.0, validation_alias="TP1_MIN_PTS")
    tp1_max_pts: float = Field(default=15.0, validation_alias="TP1_MAX_PTS")
    tp2_enable_bonus: bool = Field(default=True, validation_alias="TP2_ENABLE_BONUS")
    tp2_max_bonus_pts: float = Field(default=60.0, validation_alias="TP2_MAX_BONUS_POINTS")
    mode_trading: str = Field(default="scalp", validation_alias="MODE_TRADING")
    cooldown_minutes: int = Field(default=20, validation_alias="COOLDOWN_MINUTES")
    suivi_alerte_interval_minutes: int = Field(
        default=2, validation_alias="SUIVI_ALERTE_INTERVAL_MINUTES"
    )
    suivi_situation_interval_minutes: int = Field(
        default=5, validation_alias="SUIVI_SITUATION_INTERVAL_MINUTES"
    )
    cooldown_after_trade_minutes: int = Field(
        default=5, validation_alias="COOLDOWN_AFTER_TRADE_MINUTES"
    )
    no_go_important_cooldown_minutes: int = Field(
        default=3, validation_alias="NO_GO_IMPORTANT_COOLDOWN_MINUTES"
    )
    daily_summary_hour_paris: int = Field(
        default=22, validation_alias="DAILY_SUMMARY_HOUR_PARIS"
    )
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
    # DATA_MAX_AGE_SEC: âge max (sec) de la dernière bougie pour considérer les données OK. M15 = bougie 15 min → min 900.
    # Ne pas mettre < 900 avec TF_SIGNAL=M15 sinon DATA_OFF systématique (cf. decision_packet data_latency = bougie la plus récente).
    data_max_age_sec: int = Field(default=960, validation_alias="DATA_MAX_AGE_SEC")
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

    # Seuils de score (GO si >= go_min_score, A+ si >= a_plus_min_score)
    go_min_score: int = Field(default=80, validation_alias="GO_MIN_SCORE")
    a_plus_min_score: int = Field(default=90, validation_alias="A_PLUS_MIN_SCORE")
    # Pénalité quand momentum M15 est contre tendance (-15 par défaut). Mettre 0 pour ne plus pénaliser.
    momentum_against_penalty: int = Field(default=15, validation_alias="MOMENTUM_AGAINST_PENALTY")

    # Approche incrémentale — confirmer le setup sur plusieurs barres
    setup_confirm_min_bars: int = Field(default=2, validation_alias="SETUP_CONFIRM_MIN_BARS")
    setup_entry_tolerance_pts: float = Field(default=50.0, validation_alias="SETUP_ENTRY_TOLERANCE_PTS")

    # Suivi — distance min entre prix et S/R pour MAINTIEN (pts)
    sr_buffer_points: float = Field(default=25.0, validation_alias="SR_BUFFER_POINTS")

    # Système intelligent — state machine, phase marché, anti-extension (défaut: désactivé = comportement actuel)
    state_machine_enabled: bool = Field(default=False, validation_alias="STATE_MACHINE_ENABLED")
    extension_atr_threshold: float = Field(default=0.8, validation_alias="EXTENSION_ATR_THRESHOLD")
    cooldown_consolidation_minutes: int = Field(
        default=15, validation_alias="COOLDOWN_CONSOLIDATION_MINUTES"
    )
    cooldown_dynamic_enabled: bool = Field(default=False, validation_alias="COOLDOWN_DYNAMIC_ENABLED")
    m5_rejection_min_bars: int = Field(default=1, validation_alias="M5_REJECTION_MIN_BARS")

    def model_post_init(self, __context: Optional[dict]) -> None:  # type: ignore[override]
        self.data_provider = str(self.data_provider).lower()
        self.market_provider = str(self.market_provider).lower()
        self.log_level = str(self.log_level).upper()
        self.news_provider = str(self.news_provider).lower()
        self.trading_session_mode = str(self.trading_session_mode).lower()
        # Éviter DATA_OFF permanent : avec M15 la bougie la plus récente a 0–15 min. Forcer un minimum.
        if self.tf_signal.upper() == "M15" and self.data_max_age_sec < 900:
            self.data_max_age_sec = 900


@lru_cache
def get_settings() -> Settings:
    values = {k: v for k, v in os.environ.items()}
    return Settings(**values)
