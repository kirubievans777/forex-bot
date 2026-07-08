"""
test_indicators.py
Purpose: Confirm our indicator calculations behave correctly.
"""

import sys
import os
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from indicators import sma, ema, rsi, atr


def test_sma_basic_calculation():
    data = pd.Series([1, 2, 3, 4, 5])
    result = sma(data, window=3)
    # The 3rd value should be the average of [1, 2, 3] = 2.0
    assert result.iloc[2] == 2.0
    # The last value should be the average of [3, 4, 5] = 4.0
    assert result.iloc[4] == 4.0


def test_ema_reacts_faster_than_expected_trend():
    data = pd.Series([1, 1, 1, 1, 10])
    result = ema(data, window=3)
    # EMA should have moved noticeably toward the new value of 10
    assert result.iloc[-1] > 1


def test_rsi_range_is_valid():
    data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16])
    result = rsi(data, period=14)
    # RSI should always be between 0 and 100
    valid = result.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_rsi_strong_uptrend_is_high():
    # Consistently rising prices should push RSI toward 100
    data = pd.Series(range(1, 20))
    result = rsi(data, period=14)
    assert result.iloc[-1] > 70


def test_atr_is_non_negative():
    df = pd.DataFrame({
        "high": [1.10, 1.12, 1.11, 1.13, 1.14],
        "low": [1.08, 1.09, 1.09, 1.10, 1.11],
        "close": [1.09, 1.11, 1.10, 1.12, 1.13],
    })
    result = atr(df, period=3)
    valid = result.dropna()
    assert (valid >= 0).all()


if __name__ == "__main__":
    test_sma_basic_calculation()
    test_ema_reacts_faster_than_expected_trend()
    test_rsi_range_is_valid()
    test_rsi_strong_uptrend_is_high()
    test_atr_is_non_negative()
    print("✅ All indicator tests passed!")