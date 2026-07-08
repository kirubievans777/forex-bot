"""
test_strategy.py
Purpose: Confirm the strategy behaves correctly and safely.
"""

import sys
import os
import pandas as pd
import numpy as np

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from strategy import generate_signal, MIN_DATA_POINTS_REQUIRED, MIN_RISK_REWARD


def _make_fake_data(rows, start_price=1.1000, trend="up"):
    """Creates simple fake OHLC data for testing purposes."""
    timestamps = pd.date_range("2026-01-01", periods=rows, freq="4h", tz="UTC")

    prices = []
    price = start_price
    for _ in range(rows):
        if trend == "up":
            price += 0.0005
        elif trend == "down":
            price -= 0.0005
        prices.append(price)

    df = pd.DataFrame({
        "timestamp": timestamps,
        "open": prices,
        "high": [p + 0.0008 for p in prices],
        "low": [p - 0.0008 for p in prices],
        "close": prices,
        "volume": [1000] * rows,
    })
    return df


def test_insufficient_data_returns_no_trade():
    df = _make_fake_data(rows=5)  # Way below MIN_DATA_POINTS_REQUIRED
    decision = generate_signal(df)
    assert decision["signal"] == "NO_TRADE"
    assert decision["invalidation_reason"] is not None


def test_decision_has_all_required_fields():
    df = _make_fake_data(rows=MIN_DATA_POINTS_REQUIRED + 20, trend="up")
    decision = generate_signal(df)

    required_fields = [
        "signal", "confidence_score", "reasons_for_trade", "reasons_against_trade",
        "entry_price", "stop_loss", "take_profit", "risk_reward_ratio",
        "invalidation_reason", "timestamp",
    ]
    for field in required_fields:
        assert field in decision, f"Missing field: {field}"


def test_stop_loss_and_take_profit_are_logical_for_buy():
    # Strong, steady uptrend should produce a BUY signal (though not guaranteed
    # depending on RSI/volatility conditions in this synthetic data)
    df = _make_fake_data(rows=MIN_DATA_POINTS_REQUIRED + 30, trend="up")
    decision = generate_signal(df)

    if decision["signal"] == "BUY":
        assert decision["stop_loss"] < decision["entry_price"]
        assert decision["take_profit"] > decision["entry_price"]


def test_stop_loss_and_take_profit_are_logical_for_sell():
    df = _make_fake_data(rows=MIN_DATA_POINTS_REQUIRED + 30, trend="down")
    decision = generate_signal(df)

    if decision["signal"] == "SELL":
        assert decision["stop_loss"] > decision["entry_price"]
        assert decision["take_profit"] < decision["entry_price"]


def test_risk_reward_meets_minimum_when_trade_taken():
    df = _make_fake_data(rows=MIN_DATA_POINTS_REQUIRED + 30, trend="up")
    decision = generate_signal(df)

    if decision["signal"] in ("BUY", "SELL"):
        assert decision["risk_reward_ratio"] >= MIN_RISK_REWARD


if __name__ == "__main__":
    test_insufficient_data_returns_no_trade()
    test_decision_has_all_required_fields()
    test_stop_loss_and_take_profit_are_logical_for_buy()
    test_stop_loss_and_take_profit_are_logical_for_sell()
    test_risk_reward_meets_minimum_when_trade_taken()
    print("✅ All strategy tests passed!")