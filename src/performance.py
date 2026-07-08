"""
performance.py
Purpose: Calculate backtest performance metrics from a list of closed trades
         and an equity curve.
"""

import pandas as pd


def calculate_metrics(backtest_results):
    """
    Takes the output of run_backtest() and returns a dictionary of
    beginner-friendly performance metrics.
    """
    closed_trades = backtest_results["closed_trades"]
    equity_curve = backtest_results["equity_curve"]
    starting_balance = backtest_results["starting_balance"]
    ending_balance = backtest_results["ending_balance"]

    metrics = {
        "starting_balance": starting_balance,
        "ending_balance": ending_balance,
        "net_profit_loss": round(ending_balance - starting_balance, 2),
        "return_percent": round(
            ((ending_balance - starting_balance) / starting_balance) * 100, 2
        ),
        "number_of_trades": len(closed_trades),
    }

    if len(closed_trades) == 0:
        # No trades were taken — fill remaining metrics with safe defaults
        metrics.update({
            "win_rate_percent": None,
            "average_win": None,
            "average_loss": None,
            "profit_factor": None,
            "max_drawdown_percent": None,
            "longest_losing_streak": None,
            "average_risk_reward": None,
            "best_trade": None,
            "worst_trade": None,
            "total_trading_costs": 0,
            "time_period_start": None,
            "time_period_end": None,
        })
        return metrics

    wins = [t for t in closed_trades if t["outcome"] == "WIN"]
    losses = [t for t in closed_trades if t["outcome"] == "LOSS"]

    win_rate = (len(wins) / len(closed_trades)) * 100
    average_win = sum(t["pnl_dollars"] for t in wins) / len(wins) if wins else 0
    average_loss = sum(t["pnl_dollars"] for t in losses) / len(losses) if losses else 0

    total_wins_dollars = sum(t["pnl_dollars"] for t in wins)
    total_losses_dollars = abs(sum(t["pnl_dollars"] for t in losses))
    profit_factor = (
        round(total_wins_dollars / total_losses_dollars, 2)
        if total_losses_dollars > 0 else None
    )

    max_drawdown_percent = _calculate_max_drawdown(equity_curve)
    longest_losing_streak = _calculate_longest_losing_streak(closed_trades)

    average_risk_reward = round(
        sum(t["risk_reward_ratio"] for t in closed_trades) / len(closed_trades), 2
    )

    best_trade = max(closed_trades, key=lambda t: t["pnl_dollars"])
    worst_trade = min(closed_trades, key=lambda t: t["pnl_dollars"])

    total_trading_costs = round(
        sum(t["spread_cost_dollars"] for t in closed_trades), 2
    )

    metrics.update({
        "win_rate_percent": round(win_rate, 2),
        "average_win": round(average_win, 2),
        "average_loss": round(average_loss, 2),
        "profit_factor": profit_factor,
        "max_drawdown_percent": max_drawdown_percent,
        "longest_losing_streak": longest_losing_streak,
        "average_risk_reward": average_risk_reward,
        "best_trade": best_trade["pnl_dollars"],
        "worst_trade": worst_trade["pnl_dollars"],
        "total_trading_costs": total_trading_costs,
        "time_period_start": str(closed_trades[0]["entry_timestamp"]),
        "time_period_end": str(closed_trades[-1]["exit_timestamp"]),
    })

    return metrics


def _calculate_max_drawdown(equity_curve):
    """
    Maximum drawdown: the largest drop from a peak balance to a
    subsequent low, expressed as a percentage.
    """
    if not equity_curve:
        return 0

    balances = [point["balance"] for point in equity_curve]
    peak = balances[0]
    max_drawdown = 0

    for balance in balances:
        if balance > peak:
            peak = balance
        drawdown = (peak - balance) / peak * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    return round(max_drawdown, 2)


def _calculate_longest_losing_streak(closed_trades):
    """Longest consecutive run of losing trades, back to back."""
    longest = 0
    current = 0

    for trade in closed_trades:
        if trade["outcome"] == "LOSS":
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    return longest


def print_metrics(metrics):
    """Prints performance metrics in a clear, readable format."""
    print("\n===== BACKTEST PERFORMANCE REPORT =====")
    print(f"Starting balance:        ${metrics['starting_balance']:,.2f}")
    print(f"Ending balance:          ${metrics['ending_balance']:,.2f}")
    print(f"Net profit/loss:         ${metrics['net_profit_loss']:,.2f}")
    print(f"Return:                  {metrics['return_percent']}%")
    print(f"Number of trades:        {metrics['number_of_trades']}")

    if metrics["number_of_trades"] == 0:
        print("No trades were taken during this period.")
        print("========================================\n")
        return

    print(f"Win rate:                {metrics['win_rate_percent']}%")
    print(f"Average win:             ${metrics['average_win']:,.2f}")
    print(f"Average loss:            ${metrics['average_loss']:,.2f}")
    print(f"Profit factor:           {metrics['profit_factor']}")
    print(f"Max drawdown:            {metrics['max_drawdown_percent']}%")
    print(f"Longest losing streak:   {metrics['longest_losing_streak']} trades")
    print(f"Average risk/reward:     {metrics['average_risk_reward']}")
    print(f"Best trade:              ${metrics['best_trade']:,.2f}")
    print(f"Worst trade:             ${metrics['worst_trade']:,.2f}")
    print(f"Total trading costs:     ${metrics['total_trading_costs']:,.2f}")
    print(f"Period tested:           {metrics['time_period_start']} to {metrics['time_period_end']}")
    print("========================================\n")


if __name__ == "__main__":
    from data_loader import load_price_data
    from backtester import run_backtest

    data = load_price_data("data/processed/eurusd_h4.csv")
    results = run_backtest(data)
    metrics = calculate_metrics(results)
    print_metrics(metrics)