"""
live_runner.py
Purpose: The actual live loop - connects to the running MT5 demo
terminal, waits for each new H4 candle to close, runs our strategy on
real market data, and (if approved) executes a demo trade through
DemoTradeExecutor.

SAFETY: MT5DemoBroker and DemoTradeExecutor independently refuse to
run against anything but a demo account. This script is meant to run
in the foreground, in a terminal you keep open and can watch. Stop it
anytime with Ctrl+C.

NOTE: MT5 broker servers often report candle/tick timestamps in their
own server time, not true UTC, even though they look like standard
timestamps. On startup, this script measures the real offset between
the broker's clock and true UTC, and corrects every timestamp we read
so our session filter and logs are aligned to real-world time.
"""

import time
from datetime import datetime, timezone, timedelta
import pandas as pd

from broker_interface import MT5DemoBroker
from risk_manager import RiskManager
from demo_executor import DemoTradeExecutor
from strategy import generate_signal, MIN_DATA_POINTS_REQUIRED
from logger import log_decision, log_error

SYMBOL = "EURUSD"
PAIR_DISPLAY = "EUR/USD"
CHECK_INTERVAL_SECONDS = 60
CANDLES_TO_FETCH = MIN_DATA_POINTS_REQUIRED + 30
STARTING_BALANCE = 100_000.0
BROKER_UTC_OFFSET = timedelta(0)  # Will be recalculated at startup


def fetch_recent_candles(count=CANDLES_TO_FETCH):
    """Pulls the most recent candles from MT5 into our standard format,
    correcting timestamps to true UTC using the detected broker offset."""
    import MetaTrader5 as mt5

    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_H4, 0, count)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"Could not fetch candle data from MT5: {mt5.last_error()}")

    df = pd.DataFrame(rates)
    df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True) - BROKER_UTC_OFFSET
    df = df.rename(columns={"tick_volume": "volume"})
    return df[["timestamp", "open", "high", "low", "close", "volume"]]


def get_broker_utc_offset():
    """
    MT5 broker servers often report time in their own local server time,
    not true UTC, even though it looks like a standard timestamp. This
    calculates the real difference so we can correct for it.
    """
    import MetaTrader5 as mt5
    tick = mt5.symbol_info_tick(SYMBOL)
    broker_time = datetime.fromtimestamp(tick.time, tz=timezone.utc)
    true_utc_now = datetime.now(timezone.utc)
    offset_hours = round((broker_time - true_utc_now).total_seconds() / 3600)
    return timedelta(hours=offset_hours)


def get_latest_closed_candle(df):
    """
    MT5 includes the currently-forming candle as the last row - we only
    want to act on the last fully CLOSED candle, so we drop that row.
    """
    if len(df) < 2:
        return df, None
    closed_df = df.iloc[:-1].reset_index(drop=True)
    return closed_df, closed_df["timestamp"].iloc[-1]


def run_live_loop():
    print("=" * 60)
    print("LIVE DEMO TRADING LOOP - STARTING")
    print("=" * 60)
    print(f"Pair: {PAIR_DISPLAY}  |  Timeframe: H4  |  Checking every {CHECK_INTERVAL_SECONDS}s")
    print("Trading a DEMO account only. Press Ctrl+C to stop.\n")

    broker = MT5DemoBroker(symbol=SYMBOL)

    global BROKER_UTC_OFFSET
    BROKER_UTC_OFFSET = get_broker_utc_offset()
    print(f"Detected broker time offset from UTC: {BROKER_UTC_OFFSET}")

    risk_manager = RiskManager(starting_balance=STARTING_BALANCE)
    executor = DemoTradeExecutor(broker, risk_manager)

    account_info = broker.get_account_info()
    print(f"Connected. Balance: ${account_info['balance']:,.2f}  Mode: {account_info['mode']}\n")

    last_processed_candle_time = None

    try:
        while True:
            try:
                raw_df = fetch_recent_candles()
                closed_df, latest_closed_time = get_latest_closed_candle(raw_df)

                if latest_closed_time is None or len(closed_df) < MIN_DATA_POINTS_REQUIRED:
                    print("Not enough data yet, waiting...")
                    time.sleep(CHECK_INTERVAL_SECONDS)
                    continue

                if latest_closed_time == last_processed_candle_time:
                    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
                    print(f"[{now_str}] No new candle yet (last: {latest_closed_time}). Waiting...")
                    time.sleep(CHECK_INTERVAL_SECONDS)
                    continue

                last_processed_candle_time = latest_closed_time
                print(f"\nNew candle closed at {latest_closed_time} - evaluating...")

                price_info = broker.get_latest_price(PAIR_DISPLAY)
                decision = generate_signal(closed_df, spread_pips=price_info["spread_pips"])

                final_decision = "NO_TRADE"
                no_trade_reason = decision["invalidation_reason"] or ""

                if decision["signal"] in ("BUY", "SELL"):
                    result = executor.execute_decision(decision, current_timestamp=latest_closed_time)
                    if result["executed"]:
                        final_decision = "APPROVED"
                        print(f"TRADE EXECUTED: {decision['signal']} "
                              f"{result['position_size']} units, risking ${result['risk_amount']:.2f}")
                    else:
                        final_decision = "REJECTED"
                        reasons = result.get("reasons") or [result.get("reason", "Unknown")]
                        no_trade_reason = "; ".join(reasons)
                        print(f"Trade rejected: {no_trade_reason}")
                else:
                    print(f"No trade: {no_trade_reason}")

                log_decision({
                    "timestamp": decision["timestamp"],
                    "pair": PAIR_DISPLAY,
                    "signal": decision["signal"],
                    "confidence_score": decision["confidence_score"],
                    "reasons_for_trade": decision["reasons_for_trade"],
                    "reasons_against_trade": decision["reasons_against_trade"],
                    "no_trade_reason": no_trade_reason,
                    "spread": price_info["spread_pips"],
                    "final_decision": final_decision,
                })

            except Exception as loop_error:
                log_error(
                    error_type="LiveLoopError",
                    error_message=str(loop_error),
                    file="live_runner.py",
                    function="run_live_loop",
                    severity="HIGH",
                    action_taken="Skipped this cycle, will retry next interval.",
                )
                print(f"Error this cycle (logged, continuing): {loop_error}")

            time.sleep(CHECK_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n\nStopped by user (Ctrl+C).")
    finally:
        import MetaTrader5 as mt5
        mt5.shutdown()
        print("MT5 connection closed cleanly.")


if __name__ == "__main__":
    run_live_loop()