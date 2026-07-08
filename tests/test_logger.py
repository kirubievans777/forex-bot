"""
test_logger.py
Purpose: Confirm the logger correctly creates files, appends rows,
         and never crashes on missing fields.
"""

import sys
import os
import csv
import shutil

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

import logger

TEST_LOGS_DIR = "test_logs_temp"


def _use_test_logs_dir():
    """Redirects the logger to a temporary test folder so we never touch real logs."""
    logger.LOGS_DIR = TEST_LOGS_DIR
    logger.DECISION_LOG_PATH = os.path.join(TEST_LOGS_DIR, "decision_log.csv")
    logger.TRADE_LOG_PATH = os.path.join(TEST_LOGS_DIR, "trade_log.csv")
    logger.ERROR_LOG_PATH = os.path.join(TEST_LOGS_DIR, "error_log.csv")


def _cleanup_test_logs_dir():
    if os.path.exists(TEST_LOGS_DIR):
        shutil.rmtree(TEST_LOGS_DIR)


def test_decision_log_creates_file_with_header():
    _use_test_logs_dir()
    _cleanup_test_logs_dir()

    logger.log_decision({
        "timestamp": "2026-01-01 12:00:00",
        "pair": "EURUSD",
        "signal": "BUY",
        "confidence_score": 80,
        "reasons_for_trade": ["Trend UP", "RSI healthy"],
    })

    assert os.path.exists(logger.DECISION_LOG_PATH)

    with open(logger.DECISION_LOG_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["pair"] == "EURUSD"
        assert rows[0]["signal"] == "BUY"
        # List should have been converted to a semicolon-separated string
        assert "Trend UP" in rows[0]["reasons_for_trade"]

    _cleanup_test_logs_dir()


def test_decision_log_handles_missing_fields_gracefully():
    _use_test_logs_dir()
    _cleanup_test_logs_dir()

    # Deliberately incomplete data — should NOT raise an error
    logger.log_decision({"timestamp": "2026-01-01 12:00:00", "pair": "EURUSD"})

    with open(logger.DECISION_LOG_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert rows[0]["signal"] == ""  # Missing field filled with empty string

    _cleanup_test_logs_dir()


def test_trade_log_appends_multiple_rows():
    _use_test_logs_dir()
    _cleanup_test_logs_dir()

    logger.log_trade({"trade_id": "T1", "pair": "EURUSD", "result": "WIN", "profit_loss": 150})
    logger.log_trade({"trade_id": "T2", "pair": "EURUSD", "result": "LOSS", "profit_loss": -100})

    with open(logger.TRADE_LOG_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["trade_id"] == "T1"
        assert rows[1]["trade_id"] == "T2"

    _cleanup_test_logs_dir()


def test_error_log_never_raises_exception():
    _use_test_logs_dir()
    _cleanup_test_logs_dir()

    # Even with unusual/odd input, this should not raise an exception
    try:
        logger.log_error(
            error_type="TestError",
            error_message="Something went wrong",
            file="test_logger.py",
            function="test_error_log_never_raises_exception",
            severity="LOW",
            action_taken="Logged for review",
        )
    except Exception as e:
        assert False, f"log_error() raised an exception: {e}"

    assert os.path.exists(logger.ERROR_LOG_PATH)

    _cleanup_test_logs_dir()


if __name__ == "__main__":
    test_decision_log_creates_file_with_header()
    test_decision_log_handles_missing_fields_gracefully()
    test_trade_log_appends_multiple_rows()
    test_error_log_never_raises_exception()
    print("✅ All logger tests passed!")