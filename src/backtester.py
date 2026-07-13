"""
backtester.py
Purpose: Simulate our strategy against historical data, candle by candle,
         without using any future information (no lookahead bias).
"""

import pandas as pd
from strategy import generate_signal, MIN_DATA_POINTS_REQUIRED

STARTING_BALANCE = 100_000.0
RISK_PER_TRADE_PERCENT = 1.0     # Risk 1% of current balance per trade
ASSUMED_SPREAD_PIPS = 1.5        # Conservative assumed cost per trade
PIP_SIZE = 0.0001                # For EUR/USD, 1 pip = 0.0001


def run_backtest(df, log_no_trades=False):
    """
    Runs a full backtest over the given historical price DataFrame.

    df: pandas DataFrame with timestamp, open, high, low, close, volume,
        sorted oldest to newest.
    log_no_trades: if True, also records every NO_TRADE decision (useful
                   for review, but can be a lot of data).

    Returns a dictionary with: closed_trades, equity_curve, no_trade_log,
    starting_balance, ending_balance.
    """

    balance = STARTING_BALANCE
    equity_curve = []      # (timestamp, balance) after every candle
    closed_trades = []     # list of completed trade dictionaries
    no_trade_log = []      # optional log of every no-trade decision
    open_trade = None      # holds the currently open trade, or None

    for i in range(len(df)):
        # Only ever give the strategy data up to and including "today" (index i).
        # This is the core defense against lookahead bias.
        window = df.iloc[: i + 1]
        current_candle = df.iloc[i]

        # --- Step 1: If a trade is open, check if it should close this candle ---
        if open_trade is not None:
            closed = _check_trade_exit(open_trade, current_candle)
            if closed:
                balance += closed["pnl_dollars"]
                closed_trades.append(closed)
                open_trade = None

        # --- Step 2: If no trade is open, ask the strategy for a decision ---
        if open_trade is None and len(window) >= MIN_DATA_POINTS_REQUIRED:
            decision = generate_signal(window)

            if decision["signal"] in ("BUY", "SELL"):
                open_trade = _open_trade(decision, balance)
            elif log_no_trades:
                no_trade_log.append({
                    "timestamp": current_candle["timestamp"],
                    "reason": decision["invalidation_reason"],
                })

        # --- Step 3: Record equity at the end of this candle ---
        equity_curve.append({
            "timestamp": current_candle["timestamp"],
            "balance": balance,
        })

    # If a trade is still open at the very end of the data, close it at the
    # last available price so our numbers stay honest and complete.
    if open_trade is not None:
        forced_close = _force_close_trade(open_trade, df.iloc[-1])
        balance += forced_close["pnl_dollars"]
        closed_trades.append(forced_close)
        equity_curve[-1]["balance"] = balance

    return {
        "closed_trades": closed_trades,
        "equity_curve": equity_curve,
        "no_trade_log": no_trade_log,
        "starting_balance": STARTING_BALANCE,
        "ending_balance": balance,
    }


def _open_trade(decision, current_balance):
    """Builds a simulated open trade from a strategy decision."""
    risk_amount = current_balance * (RISK_PER_TRADE_PERCENT / 100)

    stop_distance = abs(decision["entry_price"] - decision["stop_loss"])
    spread_cost_price = ASSUMED_SPREAD_PIPS * PIP_SIZE

    # Spread cost expressed as a fraction of the risk (since we simulate
    # P/L in dollar terms proportional to risk, not literal lot sizes).
    spread_cost_fraction = spread_cost_price / stop_distance if stop_distance > 0 else 0
    spread_cost_dollars = risk_amount * spread_cost_fraction

    return {
        "direction": decision["signal"],
        "entry_price": decision["entry_price"],
        "stop_loss": decision["stop_loss"],
        "take_profit": decision["take_profit"],
        "risk_reward_ratio": decision["risk_reward_ratio"],
        "risk_amount": risk_amount,
        "spread_cost_dollars": spread_cost_dollars,
        "entry_timestamp": decision["timestamp"],
        "confidence_score": decision["confidence_score"],
    }


def _check_trade_exit(trade, candle):
    """
    Checks whether the current candle's price range would have triggered
    the trade's stop loss or take profit. Returns a closed-trade record
    if so, otherwise None.
    """
    direction = trade["direction"]
    high = candle["high"]
    low = candle["low"]

    hit_stop = False
    hit_target = False

    if direction == "BUY":
        hit_stop = low <= trade["stop_loss"]
        hit_target = high >= trade["take_profit"]
    else:  # SELL
        hit_stop = high >= trade["stop_loss"]
        hit_target = low <= trade["take_profit"]

    # Conservative assumption: if both could have happened in the same candle,
    # assume the worse outcome (stop loss) happened first.
    if hit_stop:
        return _finalize_trade(trade, candle, outcome="LOSS")
    if hit_target:
        return _finalize_trade(trade, candle, outcome="WIN")

    return None


def _finalize_trade(trade, candle, outcome):
    """Builds the final closed-trade record with profit/loss calculated."""
    if outcome == "WIN":
        pnl_dollars = (trade["risk_amount"] * trade["risk_reward_ratio"]) - trade["spread_cost_dollars"]
        exit_price = trade["take_profit"]
    else:
        pnl_dollars = -trade["risk_amount"] - trade["spread_cost_dollars"]
        exit_price = trade["stop_loss"]

    return {
        **trade,
        "exit_price": exit_price,
        "exit_timestamp": candle["timestamp"],
        "outcome": outcome,
        "pnl_dollars": round(pnl_dollars, 2),
    }


def _force_close_trade(trade, last_candle):
    """
    Closes a trade still open at the end of the dataset, using the last
    available close price (rather than leaving it dangling).
    """
    exit_price = last_candle["close"]
    direction = trade["direction"]

    if direction == "BUY":
        price_moved = exit_price - trade["entry_price"]
    else:
        price_moved = trade["entry_price"] - exit_price

    stop_distance = abs(trade["entry_price"] - trade["stop_loss"])
    fraction_of_risk = price_moved / stop_distance if stop_distance > 0 else 0
    pnl_dollars = (trade["risk_amount"] * fraction_of_risk) - trade["spread_cost_dollars"]

    outcome = "WIN" if pnl_dollars > 0 else "LOSS"

    return {
        **trade,
        "exit_price": exit_price,
        "exit_timestamp": last_candle["timestamp"],
        "outcome": outcome,
        "pnl_dollars": round(pnl_dollars, 2),
    }


if __name__ == "__main__":
    from data_loader import load_price_data

    data = load_price_data("data/processed/eurusd_h4.csv")
    results = run_backtest(data, log_no_trades=True)

    print(f"Starting balance: ${results['starting_balance']:.2f}")
    print(f"Ending balance:   ${results['ending_balance']:.2f}")
    print(f"Total trades:     {len(results['closed_trades'])}")