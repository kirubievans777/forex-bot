"""
report_generator.py
Purpose: Generate visual charts summarizing backtest performance.
"""

import matplotlib.pyplot as plt
import pandas as pd
import os


def generate_charts(backtest_results, output_dir="reports"):
    os.makedirs(output_dir, exist_ok=True)

    _plot_equity_curve(backtest_results, output_dir)
    _plot_drawdown_curve(backtest_results, output_dir)
    _plot_monthly_returns(backtest_results, output_dir)
    _plot_win_loss_distribution(backtest_results, output_dir)

    print(f"✅ Charts saved to '{output_dir}/' folder.")


def _plot_equity_curve(results, output_dir):
    equity_df = pd.DataFrame(results["equity_curve"])
    if equity_df.empty:
        return

    plt.figure(figsize=(10, 5))
    plt.plot(equity_df["timestamp"], equity_df["balance"])
    plt.title("Equity Curve")
    plt.xlabel("Time")
    plt.ylabel("Account Balance ($)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "equity_curve.png"))
    plt.close()


def _plot_drawdown_curve(results, output_dir):
    equity_df = pd.DataFrame(results["equity_curve"])
    if equity_df.empty:
        return

    balances = equity_df["balance"]
    peak = balances.cummax()
    drawdown = (peak - balances) / peak * 100

    plt.figure(figsize=(10, 5))
    plt.fill_between(equity_df["timestamp"], drawdown, color="red", alpha=0.4)
    plt.title("Drawdown Curve")
    plt.xlabel("Time")
    plt.ylabel("Drawdown (%)")
    plt.gca().invert_yaxis()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "drawdown_curve.png"))
    plt.close()


def _plot_monthly_returns(results, output_dir):
    closed_trades = results["closed_trades"]
    if not closed_trades:
        return

    trades_df = pd.DataFrame(closed_trades)
    trades_df["exit_timestamp"] = pd.to_datetime(trades_df["exit_timestamp"])
    trades_df["month"] = trades_df["exit_timestamp"].dt.to_period("M")

    monthly_pnl = trades_df.groupby("month")["pnl_dollars"].sum()

    if monthly_pnl.empty:
        return

    plt.figure(figsize=(10, 5))
    monthly_pnl.plot(kind="bar", color=["green" if v >= 0 else "red" for v in monthly_pnl])
    plt.title("Monthly Returns ($)")
    plt.xlabel("Month")
    plt.ylabel("Profit/Loss ($)")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "monthly_returns.png"))
    plt.close()


def _plot_win_loss_distribution(results, output_dir):
    closed_trades = results["closed_trades"]
    if not closed_trades:
        return

    pnl_values = [t["pnl_dollars"] for t in closed_trades]

    plt.figure(figsize=(10, 5))
    plt.hist(pnl_values, bins=15, color="steelblue", edgecolor="black")
    plt.title("Win/Loss Distribution")
    plt.xlabel("Trade Profit/Loss ($)")
    plt.ylabel("Number of Trades")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "win_loss_distribution.png"))
    plt.close()


if __name__ == "__main__":
    from data_loader import load_price_data
    from backtester import run_backtest

    data = load_price_data("data/processed/eurusd_h4.csv")
    results = run_backtest(data)
    generate_charts(results)