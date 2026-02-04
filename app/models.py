from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DecisionStatus(str, Enum):
    go = "GO"
    no_go = "NO_GO"


class BlockedBy(str, Enum):
    out_of_session = "OUT_OF_SESSION"
    news_lock = "NEWS_LOCK"
    spread_too_high = "SPREAD_TOO_HIGH"
    volatility_too_high = "VOLATILITY_TOO_HIGH"
    market_chop = "MARKET_CHOP"
    no_trend_bias = "NO_TREND_BIAS"
    bias_h1_mismatch = "BIAS_H1_MISMATCH"
    no_setup = "NO_SETUP"
    rr_too_low = "RR_TOO_LOW"
    duplicate_signal = "DUPLICATE_SIGNAL"
    daily_budget_reached = "DAILY_BUDGET_REACHED"
    data_off = "DATA_OFF"
    execution_guard = "EXECUTION_GUARD"


class Bias(str, Enum):
    up = "UP"
    down = "DOWN"
    range = "RANGE"


class Quality(str, Enum):
    a_plus = "A+"
    a = "A"
    b = "B"


class DecisionPacket(BaseModel):
    session_ok: bool
    news_lock: bool
    news_next_event: Optional[Dict[str, str]] = None
    news_impact_summary: List[str] = []
    news_next_event_details: Optional[Dict[str, Any]] = None
    news_state: Dict[str, Any] = Field(default_factory=dict)
    spread: float
    spread_max: float
    spread_ratio: Optional[float] = None
    penalties: Dict[str, Any] = Field(default_factory=dict)
    atr: float
    atr_max: float
    bias_h1: Bias
    direction: str
    setups_detected: List[str]
    proposed_entry: float
    sl: float
    tp1: float
    tp2: float
    rr_tp2: float
    rr_min: float
    tick_size: float = 0.0
    score_rules: int
    reasons_rules: List[str]
    sources_used: List[str]
    context_summary: List[str]
    state: Dict[str, Any]
    timestamps: Dict[str, Any]
    data_latency_ms: int


class DecisionAIOutput(BaseModel):
    decision: DecisionStatus
    confidence: int = Field(ge=0, le=100)
    quality: Quality
    why: List[str] = Field(max_length=3)
    notes: Optional[str] = None


class DecisionResult(BaseModel):
    status: DecisionStatus
    blocked_by: Optional[BlockedBy] = None
    score_total: int
    score_effective: int
    confidence: int
    quality: Quality
    why: List[str]


class AnalyzeRequest(BaseModel):
    symbol: Optional[str] = None


class AnalyzeResponse(BaseModel):
    decision: DecisionResult
    message: str
    decision_packet: DecisionPacket
    ai_output: Optional[DecisionAIOutput] = None
    ai_enabled: bool
    data_latency_ms: int
    ai_latency_ms: Optional[int] = None
    signal_key: str
