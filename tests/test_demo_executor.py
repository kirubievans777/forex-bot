"""
test_demo_executor.py
Purpose: Confirm the demo executor correctly enforces every safety
         check before allowing an order — using MockBroker so no
         real MT5 connection is ever needed for testing.
"""

import sys
import os
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from broker_interface import MockBroker
from risk_manager import RiskManager
from demo_executor import DemoTradeExecutor


def _good_decision():
    return {
        "signal": "BUY",
        "entry_price": 1.1000,
        "stop_loss": 1.0950,
        "take_profit": 1.1100,
        "risk_reward_ratio": 2.0,
        "confidence_score": 80,
    }


def _make_executor(starting_balance=100_000):
    broker = MockBroker(starting_balance=starting_balance)
    risk_manager = RiskManager(starting_balance=starting_balance)
    executor = DemoTradeExecutor(broker, risk_manager)
    return executor, broker, risk_manager


def test_executor_refuses_non_demo_account():
    class FakeLiveBroker(MockBroker):
        def get_account_info(self):
            info = super().get_account_info()
            info["mode"] = "live"
            return info

    broker = FakeLiveBroker()
    risk_manager = RiskManager(starting_balance=100_000)

    try:
        DemoTradeExecutor(broker, risk_manager)
        assert False, "Expected DemoTradeExecutor to refuse a non-demo account"
    except ValueError as e:
        assert "SAFETY STOP" in str(e)


def test_valid_trade_executes_successfully():
    executor, broker, risk_manager = _make_executor()
    result = executor.execute_decision(
        _good_decision(), current_timestamp=pd.Timestamp("2026-01-01 13:00")
    )
    assert result["executed"] is True
    assert len(broker.get_open_positions()) == 1


def test_no_trade_signal_is_rejected():
    executor, broker, risk_manager = _make_executor()
    decision = _good_decision()
    decision["signal"] = "NO_TRADE"

    result = executor.execute_decision(decision, current_timestamp=pd.Timestamp("2026-01-01 13:00"))
    assert result["executed"] is False


def test_low_confidence_trade_is_rejected():
    executor, broker, risk_manager = _make_executor()
    decision = _good_decision()
    decision["confidence_score"] = 10

    result = executor.execute_decision(decision, current_timestamp=pd.Timestamp("2026-01-01 13:00"))
    assert result["executed"] is False


def test_duplicate_trade_is_rejected():
    executor, broker, risk_manager = _make_executor()
    ts = pd.Timestamp("2026-01-01 13:00")

    first = executor.execute_decision(_good_decision(), current_timestamp=ts)
    assert first["executed"] is True

    second = executor.execute_decision(_good_decision(), current_timestamp=ts)
    assert second["executed"] is False
    assert any("already open" in r for r in second["reasons"])


def test_kill_switch_blocks_execution():
    executor, broker, risk_manager = _make_executor(starting_balance=100_000)
    ts = pd.Timestamp("2026-01-01 13:00")

    # Force a large loss to trip the kill switch (15%+ of 100,000 = 15,000+)
    risk_manager.record_trade_result(pnl_dollars=-20000, exit_timestamp=ts)

    result = executor.execute_decision(_good_decision(), current_timestamp=ts)
    assert result["executed"] is False


def test_wide_spread_blocks_execution():
    executor, broker, risk_manager = _make_executor()
    broker.simulated_spread_pips = 5.0  # Force spread above our 2.0 pip limit

    result = executor.execute_decision(
        _good_decision(), current_timestamp=pd.Timestamp("2026-01-01 13:00")
    )
    assert result["executed"] is False
    assert any("Spread too high" in r for r in result["reasons"])


if __name__ == "__main__":
    test_executor_refuses_non_demo_account()
    test_valid_trade_executes_successfully()
    test_no_trade_signal_is_rejected()
    test_low_confidence_trade_is_rejected()
    test_duplicate_trade_is_rejected()
    test_kill_switch_blocks_execution()
    test_wide_spread_blocks_execution()
    print("✅ All demo executor tests passed!")