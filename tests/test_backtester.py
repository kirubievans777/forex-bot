"""
test_backtester.py
Purpose: Confirm the backtester behaves safely and correctly.
"""

import sys
import os
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from backtester import run_backtest, STARTING_BALANCE
from strategy import MIN_DATA_POINTS_REQUIRED


def _make_fake_data(rows, trend="up"):
    timestamps = pd.date_range("2026-01-01", periods=rows, freq="4h", tz="UTC")
    prices = []
    price = 1.1000
    for _ in range(rows):
        price += 0.0005 if trend == "up" else -0.0005
        prices.append(price)

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": prices,
        "high": [p + 0.0008 for p in prices],
        "low": [p - 0.0008 for p in prices],
        "close": prices,
        "volume": [1000] * rows,
    })


def test_no_trades_with_insufficient_data():
    df = _make_fake_data(rows=5)
    results = run_backtest(df)
    assert len(results["closed_trades"]) == 0
    assert results["ending_balance"] == STARTING_BALANCE


def test_only_one_trade_open_at_a_time():
    df = _make_fake_data(rows=MIN_DATA_POINTS_REQUIRED + 100, trend="up")
    results = run_backtest(df)

    # Check that no two trades overlap in time
    trades = sorted(results["closed_trades"], key=lambda t: t["entry_timestamp"])
    for i in range(len(trades) - 1):
        assert trades[i]["exit_timestamp"] <= trades[i + 1]["entry_timestamp"], (
            "Found overlapping trades — only one should be open at a time."
        )


def test_equity_curve_matches_data_length():
    df = _make_fake_data(rows=MIN_DATA_POINTS_REQUIRED + 50, trend="up")
    results = run_backtest(df)
    assert len(results["equity_curve"]) == len(df)


def test_balance_never_goes_negative_infinite():
    # Sanity check: balance should stay a real, finite number throughout
    df = _make_fake_data(rows=MIN_DATA_POINTS_REQUIRED + 50, trend="down")
    results = run_backtest(df)
    for point in results["equity_curve"]:
        assert point["balance"] == point["balance"]  # NaN check (NaN != NaN)
        assert point["balance"] > -1_000_000  # sanity bound, not a real business rule


if __name__ == "__main__":
    test_no_trades_with_insufficient_data()
    test_only_one_trade_open_at_a_time()
    test_equity_curve_matches_data_length()
    test_balance_never_goes_negative_infinite()
    print("✅ All backtester tests passed!")