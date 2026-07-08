"""
logger.py
Purpose: Write structured decision, trade, and error logs to CSV files.
         Designed to never crash the bot even if a field is missing.
"""

import os
import csv
from datetime import datetime, timezone

LOGS_DIR = "logs"

DECISION_LOG_PATH = os.path.join(LOGS_DIR, "decision_log.csv")
TRADE_LOG_PATH = os.path.join(LOGS_DIR, "trade_log.csv")
ERROR_LOG_PATH = os.path.join(LOGS_DIR, "error_log.csv")

DECISION_LOG_COLUMNS = [
    "timestamp", "pair", "signal", "confidence_score",
    "reasons_for_trade", "reasons_against_trade", "no_trade_reason",
    "trend_condition", "rsi_value", "atr_value", "volatility_condition",
    "session", "spread", "final_decision",
]

TRADE_LOG_COLUMNS = [
    "trade_id", "entry_time", "exit_time", "pair", "direction",
    "entry_price", "stop_loss", "take_profit", "position_size",
    "risk_amount", "exit_price", "result", "profit_loss",
    "risk_reward_planned", "risk_reward_actual", "strategy_version", "notes",
]

ERROR_LOG_COLUMNS = [
    "timestamp", "error_type", "error_message", "file",
    "function", "severity", "action_taken",
]


def _ensure_log_exists(filepath, columns):
    """Creates the log file with a header row if it doesn't already exist."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    if not os.path.exists(filepath):
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()


def _safe_row(data, columns):
    """
    Builds a row dictionary from `data`, filling in any missing fields
    with an empty string instead of crashing. Also converts lists
    (like reasons_for_trade) into a readable semicolon-separated string.
    """
    row = {}
    for col in columns:
        value = data.get(col, "")
        if isinstance(value, list):
            value = "; ".join(str(v) for v in value)
        if value is None:
            value = ""
        row[col] = value
    return row


def log_decision(decision_data):
    """
    Appends one row to the decision log.
    decision_data: dictionary with keys matching (a subset of)
                   DECISION_LOG_COLUMNS. Missing keys are filled safely.
    """
    _ensure_log_exists(DECISION_LOG_PATH, DECISION_LOG_COLUMNS)
    row = _safe_row(decision_data, DECISION_LOG_COLUMNS)

    with open(DECISION_LOG_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DECISION_LOG_COLUMNS)
        writer.writerow(row)


def log_trade(trade_data):
    """
    Appends one row to the trade log.
    trade_data: dictionary with keys matching (a subset of)
                TRADE_LOG_COLUMNS. Missing keys are filled safely.
    """
    _ensure_log_exists(TRADE_LOG_PATH, TRADE_LOG_COLUMNS)
    row = _safe_row(trade_data, TRADE_LOG_COLUMNS)

    with open(TRADE_LOG_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRADE_LOG_COLUMNS)
        writer.writerow(row)


def log_error(error_type, error_message, file, function, severity="MEDIUM", action_taken=""):
    """
    Appends one row to the error log. This should never itself raise an
    exception — logging a problem should never create a bigger problem.
    """
    try:
        _ensure_log_exists(ERROR_LOG_PATH, ERROR_LOG_COLUMNS)
        row = _safe_row({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type,
            "error_message": str(error_message),
            "file": file,
            "function": function,
            "severity": severity,
            "action_taken": action_taken,
        }, ERROR_LOG_COLUMNS)

        with open(ERROR_LOG_PATH, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=ERROR_LOG_COLUMNS)
            writer.writerow(row)
    except Exception:
        # Last-resort fallback: print to console rather than crash the bot
        # because logging itself failed.
        print(f"⚠️ Failed to write to error log. Original error: {error_message}")