"""
journal.py
Purpose: Read and summarize the logs created by logger.py — turning raw
         rows into beginner-friendly insights about bot performance
         and behavior.
"""

import pandas as pd
import os

from logger import DECISION_LOG_PATH, TRADE_LOG_PATH


def summarize_trades(trade_log_path=TRADE_LOG_PATH):
    """
    Summarizes the trade log: win rate, most/least profitable patterns,
    average confidence, etc.
    """
    if not os.path.exists(trade_log_path):
        return {"message": "No trade log found yet — no trades have been recorded."}

    df = pd.read_csv(trade_log_path)

    if df.empty:
        return {"message": "Trade log exists but is empty — no trades recorded yet."}

    total_trades = len(df)
    wins = df[df["result"] == "WIN"]
    losses = df[df["result"] == "LOSS"]

    win_rate = round((len(wins) / total_trades) * 100, 2) if total_trades > 0 else 0

    summary = {
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_percent": win_rate,
    }

    if "profit_loss" in df.columns and not df["profit_loss"].isnull().all():
        profitable = df[df["profit_loss"] > 0]
        unprofitable = df[df["profit_loss"] <= 0]

        summary["average_profit_loss"] = round(df["profit_loss"].mean(), 2)

        if not profitable.empty:
            summary["best_trade_id"] = profitable.loc[profitable["profit_loss"].idxmax(), "trade_id"]
            summary["best_trade_pnl"] = round(profitable["profit_loss"].max(), 2)
        if not unprofitable.empty:
            summary["worst_trade_id"] = unprofitable.loc[unprofitable["profit_loss"].idxmin(), "trade_id"]
            summary["worst_trade_pnl"] = round(unprofitable["profit_loss"].min(), 2)

    return summary


def summarize_decisions(decision_log_path=DECISION_LOG_PATH):
    """
    Summarizes the decision log: most common no-trade reasons, most
    common rejection reasons, average confidence score.
    """
    if not os.path.exists(decision_log_path):
        return {"message": "No decision log found yet — no decisions have been recorded."}

    df = pd.read_csv(decision_log_path)

    if df.empty:
        return {"message": "Decision log exists but is empty."}

    summary = {
        "total_decisions_logged": len(df),
    }

    if "confidence_score" in df.columns:
        numeric_scores = pd.to_numeric(df["confidence_score"], errors="coerce").dropna()
        if not numeric_scores.empty:
            summary["average_confidence_score"] = round(numeric_scores.mean(), 2)

    if "no_trade_reason" in df.columns:
        reasons = df["no_trade_reason"].replace("", pd.NA).dropna()
        if not reasons.empty:
            summary["most_common_no_trade_reason"] = reasons.mode()[0]
            summary["no_trade_reason_counts"] = reasons.value_counts().to_dict()

    if "final_decision" in df.columns:
        rejected = df[df["final_decision"] == "REJECTED"]
        if not rejected.empty and "no_trade_reason" in df.columns:
            rejection_reasons = rejected["no_trade_reason"].replace("", pd.NA).dropna()
            if not rejection_reasons.empty:
                summary["most_common_rejection_reason"] = rejection_reasons.mode()[0]

    if "signal" in df.columns:
        summary["signal_counts"] = df["signal"].value_counts().to_dict()

    return summary


def print_summary(summary, title="Summary"):
    """Prints a summary dictionary in a clean, readable format."""
    print(f"\n--- {title} ---")
    if "message" in summary:
        print(summary["message"])
        print("---\n")
        return

    for key, value in summary.items():
        if isinstance(value, dict):
            print(f"{key}:")
            for sub_key, sub_value in value.items():
                print(f"   {sub_key}: {sub_value}")
        else:
            print(f"{key}: {value}")
    print("---\n")


if __name__ == "__main__":
    trade_summary = summarize_trades()
    print_summary(trade_summary, title="Trade Summary")

    decision_summary = summarize_decisions()
    print_summary(decision_summary, title="Decision Summary")