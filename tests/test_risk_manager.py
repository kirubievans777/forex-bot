"""
test_risk_manager.py
Purpose: Confirm the risk manager correctly enforces every rule.
"""

import sys
import os
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from risk_manager import RiskManager, calculate_position_size, MIN_CONFIDENCE_SCORE


def _good_decision(confidence=80, risk_reward=2.0):
    return {
        "entry_price": 1.1000,
        "stop_loss": 1.0950,
        "take_profit": 1.1100,
        "risk_reward_ratio": risk_reward,
        "confidence_score": confidence,
    }


def test_position_sizing_basic_math():
    result = calculate_position_size(
        account_balance=10_000, risk_percent=1.0,
        entry_price=1.1000, stop_loss_price=1.0950,
    )
    # Risk amount should be exactly 1% of balance
    assert result["risk_amount"] == 100.0
    # Stop distance should be 0.0050
    assert result["stop_distance"] == 0.005


def test_position_sizing_flags_zero_stop_distance():
    result = calculate_position_size(
        account_balance=10_000, risk_percent=1.0,
        entry_price=1.1000, stop_loss_price=1.1000,  # same as entry — invalid
    )
    assert result["position_size"] == 0
    assert result["warning"] is not None


def test_trade_approved_under_normal_conditions():
    rm = RiskManager(starting_balance=10_000)
    result = rm.validate_trade(_good_decision(), current_timestamp=pd.Timestamp("2026-01-01 12:00"))
    assert result["approved"] is True
    assert result["position_size"] > 0
    assert result["kill_switch_status"] == "INACTIVE"


def test_trade_rejected_low_confidence():
    rm = RiskManager(starting_balance=10_000)
    decision = _good_decision(confidence=MIN_CONFIDENCE_SCORE - 1)
    result = rm.validate_trade(decision, current_timestamp=pd.Timestamp("2026-01-01 12:00"))
    assert result["approved"] is False
    assert any("Confidence" in r for r in result["rejection_reasons"])


def test_trade_rejected_low_risk_reward():
    rm = RiskManager(starting_balance=10_000)
    decision = _good_decision(risk_reward=1.0)  # below our 1.5 minimum
    result = rm.validate_trade(decision, current_timestamp=pd.Timestamp("2026-01-01 12:00"))
    assert result["approved"] is False
    assert any("Risk/reward" in r for r in result["rejection_reasons"])


def test_max_trades_per_day_enforced():
    rm = RiskManager(starting_balance=10_000)
    ts = pd.Timestamp("2026-01-01 12:00")

    # Simulate 3 trades already happening today
    for _ in range(3):
        rm.record_trade_result(pnl_dollars=10, exit_timestamp=ts)

    result = rm.validate_trade(_good_decision(), current_timestamp=ts)
    assert result["approved"] is False
    assert any("Maximum trades per day" in r for r in result["rejection_reasons"])


def test_consecutive_losses_trigger_rejection():
    rm = RiskManager(starting_balance=10_000)
    ts = pd.Timestamp("2026-01-01 12:00")

    for _ in range(4):
        rm.record_trade_result(pnl_dollars=-50, exit_timestamp=ts)

    result = rm.validate_trade(_good_decision(), current_timestamp=ts)
    assert result["approved"] is False
    assert any("Consecutive losses" in r for r in result["rejection_reasons"])


def test_daily_loss_limit_enforced():
    rm = RiskManager(starting_balance=10_000)
    ts = pd.Timestamp("2026-01-01 12:00")

    # 3% of 10,000 = 300 — simulate hitting that in one loss
    rm.record_trade_result(pnl_dollars=-300, exit_timestamp=ts)

    result = rm.validate_trade(_good_decision(), current_timestamp=ts)
    assert result["approved"] is False
    assert any("Daily loss limit" in r for r in result["rejection_reasons"])


def test_kill_switch_activates_on_max_drawdown():
    rm = RiskManager(starting_balance=10_000)
    ts = pd.Timestamp("2026-01-01 12:00")

    # Simulate a large loss that pushes drawdown past 15%
    rm.record_trade_result(pnl_dollars=-2000, exit_timestamp=ts)

    result = rm.validate_trade(_good_decision(), current_timestamp=ts)
    assert result["kill_switch_status"] == "ACTIVE"
    assert result["approved"] is False


def test_kill_switch_blocks_all_trades_until_reset():
    rm = RiskManager(starting_balance=10_000)
    ts = pd.Timestamp("2026-01-01 12:00")
    rm.record_trade_result(pnl_dollars=-2000, exit_timestamp=ts)  # 20% drawdown

    # Confirm it's blocked
    result = rm.validate_trade(_good_decision(), current_timestamp=ts)
    assert result["approved"] is False
    assert result["kill_switch_status"] == "ACTIVE"

    # Reset the switch itself...
    rm.reset_kill_switch()
    assert rm.kill_switch_active is False

    # ...but the account is STILL 20% underwater, so the very next check
    # correctly re-triggers the kill switch. This is intentional protective
    # behavior: a manual reset alone should never bypass a real, ongoing
    # drawdown problem.
    result_after_reset = rm.validate_trade(_good_decision(), current_timestamp=ts)
    assert result_after_reset["kill_switch_status"] == "ACTIVE"
    assert result_after_reset["approved"] is False


def test_kill_switch_stays_inactive_after_genuine_recovery():
    rm = RiskManager(starting_balance=10_000)
    ts = pd.Timestamp("2026-01-01 12:00")

    rm.record_trade_result(pnl_dollars=-2000, exit_timestamp=ts)  # -20% drawdown, kill switch trips
    rm.reset_kill_switch()

    # Balance genuinely recovers this time (e.g. a winning trade)
    rm.record_trade_result(pnl_dollars=1500, exit_timestamp=ts)  # drawdown now only 5%
    rm.reset_kill_switch()  # clear the flag now that we're actually recovered

    result = rm.validate_trade(_good_decision(), current_timestamp=ts)
    assert result["kill_switch_status"] == "INACTIVE"


def test_minimum_balance_blocks_trading():
    # Chosen so balance drops below the $1,000 minimum WITHOUT also
    # crossing the 15% max drawdown limit, so we isolate this one rule.
    rm = RiskManager(starting_balance=1_050)
    ts = pd.Timestamp("2026-01-01 12:00")
    rm.record_trade_result(pnl_dollars=-150, exit_timestamp=ts)  # balance = 900, drawdown ~14.3%

    result = rm.validate_trade(_good_decision(), current_timestamp=ts)
    assert result["approved"] is False
    assert any("below minimum required" in r for r in result["rejection_reasons"])


if __name__ == "__main__":
    test_position_sizing_basic_math()
    test_position_sizing_flags_zero_stop_distance()
    test_trade_approved_under_normal_conditions()
    test_trade_rejected_low_confidence()
    test_trade_rejected_low_risk_reward()
    test_max_trades_per_day_enforced()
    test_consecutive_losses_trigger_rejection()
    test_daily_loss_limit_enforced()
    test_kill_switch_activates_on_max_drawdown()
    test_kill_switch_blocks_all_trades_until_reset()
    test_kill_switch_stays_inactive_after_genuine_recovery()
    test_minimum_balance_blocks_trading()
    print("✅ All risk manager tests passed!")