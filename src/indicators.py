"""
indicators.py
Purpose: Calculate the technical indicators our strategy needs —
         moving averages, RSI, and ATR — using only pandas/numpy.
"""

import pandas as pd
import numpy as np


def sma(series, window):
    """Simple Moving Average: plain average of the last `window` values."""
    return series.rolling(window=window).mean()


def ema(series, window):
    """
    Exponential Moving Average: like SMA, but gives more weight to
    recent prices, so it reacts a bit faster to new information.
    """
    return series.ewm(span=window, adjust=False).mean()


def rsi(series, period=14):
    """
    Relative Strength Index (0-100).
    Measures how strongly recent price changes have leaned up vs down.
    """
    delta = series.diff()

    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    avg_gain = gains.rolling(window=period).mean()
    avg_loss = losses.rolling(window=period).mean()

    # Avoid division by zero
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_values = 100 - (100 / (1 + rs))

    # Where avg_loss is 0 and avg_gain > 0, RSI should be 100 (pure strength)
    rsi_values = rsi_values.fillna(100)

    return rsi_values


def atr(df, period=14):
    """
    Average True Range: average size of price movement per candle,
    accounting for gaps between candles. Used to size stop losses
    realistically based on current volatility.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    # "True range" is the largest of these three measurements
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    return true_range.rolling(window=period).mean()