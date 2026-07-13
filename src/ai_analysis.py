"""
ai_analysis.py
Purpose: Prepare structured, safe summaries of bot decisions, trades,
         and backtest results — formatted for a human to paste into
         Claude (or, later, send via API) for advisory analysis only.

IMPORTANT: This file does NOT call any AI API and does NOT place,
modify, or influence any trade. It only formats existing data.
"""

import pandas as pd
import os

from logger import DECISION_LOG_PATH, TRADE_LOG_PATH


def prepare_trade_explanation_input(decision):
    """
    Formats a single strategy decision dictionary into a clean,
    readable block of text — ready to paste into the Trade Explanation
    Prompt template.
    """
    lines = [
        "=== TRADE DECISION DATA ===",
        f"Timestamp: {decision.get('timestamp')}",
        f"Signal: {decision.get('signal')}",
        f"Confidence score: {decision.get('confidence_score')}",
        f"Entry price: {decision.get('entry_price')}",
        f"Stop loss: {decision.get('stop_loss')}",
        f"Take profit: {decision.get('take_profit')}",
        f"Risk/reward ratio: {decision.get('risk_reward_ratio')}",
        f"Reasons for trade: {'; '.join(decision.get('reasons_for_trade', []))}",
        f"Reasons against trade: {'; '.join(decision.get('reasons_against_trade', []))}",
        f"Invalidation reason: {decision.get('invalidation_reason')}",
    ]
    return "\n".join(lines)


def prepare_backtest_review_input(metrics, data_start=None, data_end=None, num_candles=None):
    """
    Formats backtest performance metrics into a clean block of text —
    ready to paste into the Backtest Review Prompt template.
    """
    lines = ["=== BACKTEST PERFORMANCE DATA ==="]

    if num_candles is not None:
        lines.append(f"Candles tested: {num_candles}")
    if data_start is not None and data_end is not None:
        lines.append(f"Date range tested: {data_start} to {data_end}")

    for key, value in metrics.items():
        readable_key = key.replace("_", " ").capitalize()
        lines.append(f"{readable_key}: {value}")

    return "\n".join(lines)


def prepare_journal_review_input(trade_summary, decision_summary):
    """
    Formats trade and decision summaries (from journal.py) into a
    clean block of text — ready to paste into the Trade Journal
    Review Prompt template.
    """
    lines = ["=== TRADE JOURNAL SUMMARY ==="]

    lines.append("\n--- Trade Summary ---")
    for key, value in trade_summary.items():
        readable_key = key.replace("_", " ").capitalize()
        lines.append(f"{readable_key}: {value}")

    lines.append("\n--- Decision Summary ---")
    for key, value in decision_summary.items():
        readable_key = key.replace("_", " ").capitalize()
        if isinstance(value, dict):
            lines.append(f"{readable_key}:")
            for sub_key, sub_value in value.items():
                lines.append(f"   {sub_key}: {sub_value}")
        else:
            lines.append(f"{readable_key}: {value}")

    return "\n".join(lines)


def prepare_risk_audit_input(risk_config, recent_test_results_summary=""):
    """
    Formats the risk manager's configuration into a clean block of
    text — ready to paste into the Risk Audit Prompt template.

    risk_config: dictionary of rule names -> values (see example usage
                 at the bottom of this file).
    recent_test_results_summary: optional free-text note on test coverage.
    """
    lines = ["=== RISK CONFIGURATION ==="]

    for key, value in risk_config.items():
        readable_key = key.replace("_", " ").capitalize()
        lines.append(f"{readable_key}: {value}")

    if recent_test_results_summary:
        lines.append("\n--- Test Coverage Notes ---")
        lines.append(recent_test_results_summary)

    return "\n".join(lines)


def prepare_code_review_input(filepath, change_description=""):
    """
    Reads a source code file and formats it (with the change
    description) into a clean block of text — ready to paste into the
    Code Review Prompt template.

    Note: this only reads and formats code; it never executes,
    modifies, or evaluates the code in any way.
    """
    if not os.path.exists(filepath):
        return f"Error: file not found at {filepath}"

    with open(filepath, "r", encoding="utf-8") as f:
        code_content = f.read()

    lines = [
        "=== CODE FOR REVIEW ===",
        f"File: {filepath}",
    ]
    if change_description:
        lines.append(f"Change description: {change_description}")

    lines.append("\n--- Code ---")
    lines.append(code_content)

    return "\n".join(lines)


def load_recent_decisions(n=10, decision_log_path=DECISION_LOG_PATH):
    """
    Loads the most recent N rows from the decision log, useful for
    batch review (e.g. feeding several recent decisions into a
    Journal Review session at once).
    """
    if not os.path.exists(decision_log_path):
        return []

    df = pd.read_csv(decision_log_path)
    if df.empty:
        return []

    recent = df.tail(n)
    return recent.to_dict(orient="records")


if __name__ == "__main__":
    # Example / manual test usage — demonstrates the output format
    # without needing real logs to exist yet.
    example_decision = {
        "timestamp": "2026-07-06 13:00:00+00:00",
        "signal": "BUY",
        "confidence_score": 80,
        "entry_price": 1.14329,
        "stop_loss": 1.14204,
        "take_profit": 1.14517,
        "risk_reward_ratio": 1.5,
        "reasons_for_trade": ["Trend is UP", "RSI does not contradict BUY"],
        "reasons_against_trade": [],
        "invalidation_reason": None,
    }

    print(prepare_trade_explanation_input(example_decision))
    print("\n\n")

    example_metrics = {
        "starting_balance": 10000,
        "ending_balance": 10250,
        "net_profit_loss": 250,
        "return_percent": 2.5,
        "number_of_trades": 4,
        "win_rate_percent": 75.0,
        "max_drawdown_percent": 3.2,
    }
    print(prepare_backtest_review_input(
        example_metrics, data_start="2026-06-07", data_end="2026-07-06", num_candles=124
    ))