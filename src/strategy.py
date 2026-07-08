"""
strategy.py
Purpose: Version 1 rule-based trading strategy for EUR/USD.
         Analyzes recent price data and returns a trade decision —
         BUY, SELL, or NO_TRADE — along with full reasoning.
"""

import pandas as pd
from indicators import ema, rsi, atr

# --- Strategy configuration (easy to adjust later) ---
FAST_MA_PERIOD = 20
SLOW_MA_PERIOD = 50
RSI_PERIOD = 14
ATR_PERIOD = 14

RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

MIN_ATR_PERCENT = 0.05   # Minimum volatility, as % of price (too quiet below this)
MAX_ATR_PERCENT = 1.0    # Maximum volatility, as % of price (too wild above this)

STOP_LOSS_ATR_MULTIPLIER = 1.5
MIN_RISK_REWARD = 1.5

SESSION_START_HOUR_UTC = 12   # London/New York overlap start
SESSION_END_HOUR_UTC = 16     # London/New York overlap end

MAX_SPREAD_PIPS = 2.0  # Only used if spread data is present in the dataframe

MIN_DATA_POINTS_REQUIRED = SLOW_MA_PERIOD + 5  # Buffer for indicator warm-up


def _build_decision(
    signal="NO_TRADE",
    confidence_score=0,
    reasons_for_trade=None,
    reasons_against_trade=None,
    entry_price=None,
    stop_loss=None,
    take_profit=None,
    risk_reward_ratio=None,
    invalidation_reason=None,
    timestamp=None,
):
    """Builds the standard trade decision dictionary every call returns."""
    return {
        "signal": signal,
        "confidence_score": confidence_score,
        "reasons_for_trade": reasons_for_trade or [],
        "reasons_against_trade": reasons_against_trade or [],
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_reward_ratio": risk_reward_ratio,
        "invalidation_reason": invalidation_reason,
        "timestamp": timestamp,
    }


def generate_signal(df, spread_pips=None):
    """
    Analyzes the most recent candle in `df` and returns a trade decision.

    df: a pandas DataFrame with columns timestamp, open, high, low, close, volume
        (must be sorted oldest to newest).
    spread_pips: optional current spread, in pips, if available.
    """

    # --- No-trade condition: not enough data ---
    if len(df) < MIN_DATA_POINTS_REQUIRED:
        return _build_decision(
            invalidation_reason=(
                f"Insufficient data: need at least {MIN_DATA_POINTS_REQUIRED} "
                f"candles, have {len(df)}."
            ),
            timestamp=df["timestamp"].iloc[-1] if len(df) > 0 else None,
        )

    # --- No-trade condition: missing/invalid price values in latest candle ---
    latest = df.iloc[-1]
    if latest[["open", "high", "low", "close"]].isnull().any():
        return _build_decision(
            invalidation_reason="Missing or invalid price data in latest candle.",
            timestamp=latest["timestamp"],
        )

    # --- Calculate indicators ---
    fast_ma = ema(df["close"], FAST_MA_PERIOD)
    slow_ma = ema(df["close"], SLOW_MA_PERIOD)
    rsi_values = rsi(df["close"], RSI_PERIOD)
    atr_values = atr(df, ATR_PERIOD)

    latest_fast_ma = fast_ma.iloc[-1]
    latest_slow_ma = slow_ma.iloc[-1]
    latest_rsi = rsi_values.iloc[-1]
    latest_atr = atr_values.iloc[-1]
    latest_close = latest["close"]
    latest_timestamp = latest["timestamp"]

    reasons_for = []
    reasons_against = []

    # --- Trend detection ---
    ma_gap_percent = abs(latest_fast_ma - latest_slow_ma) / latest_close * 100
    trend_unclear = ma_gap_percent < 0.02  # Fast/slow MAs too close together

    if trend_unclear:
        return _build_decision(
            invalidation_reason="Trend unclear: fast and slow moving averages too close together.",
            timestamp=latest_timestamp,
        )

    trend_direction = "UP" if latest_fast_ma > latest_slow_ma else "DOWN"
    proposed_signal = "BUY" if trend_direction == "UP" else "SELL"
    reasons_for.append(f"Trend is {trend_direction} (fast MA vs slow MA).")

    # --- Momentum (RSI) filter ---
    if proposed_signal == "BUY" and latest_rsi > RSI_OVERBOUGHT:
        return _build_decision(
            invalidation_reason=f"RSI overbought ({latest_rsi:.1f}) — avoiding BUY entry.",
            timestamp=latest_timestamp,
        )
    if proposed_signal == "SELL" and latest_rsi < RSI_OVERSOLD:
        return _build_decision(
            invalidation_reason=f"RSI oversold ({latest_rsi:.1f}) — avoiding SELL entry.",
            timestamp=latest_timestamp,
        )
    reasons_for.append(f"RSI ({latest_rsi:.1f}) does not contradict {proposed_signal}.")

    # --- Volatility filter (ATR as % of price) ---
    atr_percent = (latest_atr / latest_close) * 100
    if atr_percent < MIN_ATR_PERCENT:
        return _build_decision(
            invalidation_reason=f"Volatility too low (ATR {atr_percent:.3f}% of price).",
            timestamp=latest_timestamp,
        )
    if atr_percent > MAX_ATR_PERCENT:
        return _build_decision(
            invalidation_reason=f"Volatility too high (ATR {atr_percent:.3f}% of price).",
            timestamp=latest_timestamp,
        )
    reasons_for.append(f"Volatility is within acceptable range (ATR {atr_percent:.3f}% of price).")

    # --- Session filter ---
    hour_utc = pd.Timestamp(latest_timestamp).hour
    in_session = SESSION_START_HOUR_UTC <= hour_utc < SESSION_END_HOUR_UTC
    if not in_session:
        return _build_decision(
            invalidation_reason=(
                f"Outside preferred trading session (hour {hour_utc} UTC not in "
                f"{SESSION_START_HOUR_UTC}-{SESSION_END_HOUR_UTC} UTC)."
            ),
            timestamp=latest_timestamp,
        )
    reasons_for.append("Within preferred trading session (London/New York overlap).")

    # --- Spread filter (only if spread data provided) ---
    if spread_pips is not None:
        if spread_pips > MAX_SPREAD_PIPS:
            return _build_decision(
                invalidation_reason=f"Spread too wide ({spread_pips} pips).",
                timestamp=latest_timestamp,
            )
        reasons_for.append(f"Spread ({spread_pips} pips) is acceptable.")
    else:
        reasons_against.append("Spread data not available — filter inactive for this run.")

    # --- Stop loss / take profit / risk-reward ---
    entry_price = latest_close
    stop_distance = latest_atr * STOP_LOSS_ATR_MULTIPLIER

    if proposed_signal == "BUY":
        stop_loss = entry_price - stop_distance
        take_profit = entry_price + (stop_distance * MIN_RISK_REWARD)
    else:  # SELL
        stop_loss = entry_price + stop_distance
        take_profit = entry_price - (stop_distance * MIN_RISK_REWARD)

    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    risk_reward_ratio = round(reward / risk, 2) if risk > 0 else 0

    if risk_reward_ratio < MIN_RISK_REWARD:
        return _build_decision(
            invalidation_reason=f"Risk/reward ({risk_reward_ratio}) below minimum ({MIN_RISK_REWARD}).",
            timestamp=latest_timestamp,
        )
    reasons_for.append(f"Risk/reward ratio ({risk_reward_ratio}) meets minimum requirement.")

    # --- Confidence score: count how many conditions aligned ---
    # Each confirmed reason_for contributes points; capped at 100.
    points_per_reason = 100 // 5  # 5 core checks: trend, rsi, volatility, session, risk/reward
    confidence_score = min(100, len(reasons_for) * points_per_reason)

    return _build_decision(
        signal=proposed_signal,
        confidence_score=confidence_score,
        reasons_for_trade=reasons_for,
        reasons_against_trade=reasons_against,
        entry_price=round(entry_price, 5),
        stop_loss=round(stop_loss, 5),
        take_profit=round(take_profit, 5),
        risk_reward_ratio=risk_reward_ratio,
        invalidation_reason=None,
        timestamp=latest_timestamp,
    )