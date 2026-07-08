"""
test_performance.py
Purpose: Confirm performance metrics are calculated correctly using
         small, known example data.
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from performance import calculate_metrics


def _make_fake_backtest_results():
    """A small, hand-crafted set of trades with known, easy-to-verify outcomes."""
    closed_trades = [
        {
            "entry_timestamp": "2026-01-01", "exit_timestamp": "2026-01-02",
            "outcome": "WIN", "pnl_dollars": 150.0, "risk_reward_ratio": 1.5,
            "spread_cost_dollars": 2.0,
        },
        {
            "entry_timestamp": "2026-01-03", "exit_timestamp": "2026-01-04",
            "outcome": "LOSS", "pnl_dollars": -100.0, "risk_reward_ratio": 1.5,
            "spread_cost_dollars": 2.0,
        },
        {
            "entry_timestamp": "2026-01-05", "exit_timestamp": "2026-01-06",
            "outcome": "WIN", "pnl_dollars": 150.0, "risk_reward_ratio": 1.5,
            "spread_cost_dollars": 2.0,
        },
    ]

    equity_curve = [
        {"timestamp": "2026-01-01", "balance": 10000},
        {"timestamp": "2026-01-02", "balance": 10150},
        {"timestamp": "2026-01-03", "balance": 10150},
        {"timestamp": "2026-01-04", "balance": 10050},
        {"timestamp": "2026-01-05", "balance": 10050},
        {"timestamp": "2026-01-06", "balance": 10200},
    ]

    return {
        "closed_trades": closed_trades,
        "equity_curve": equity_curve,
        "starting_balance": 10000,
        "ending_balance": 10200,
    }


def test_basic_metrics_are_correct():
    results = _make_fake_backtest_results()
    metrics = calculate_metrics(results)

    assert metrics["number_of_trades"] == 3
    assert metrics["net_profit_loss"] == 200.0
    assert metrics["win_rate_percent"] == round(2 / 3 * 100, 2)


def test_profit_factor_calculation():
    results = _make_fake_backtest_results()
    metrics = calculate_metrics(results)

    # Total wins = 300, total losses = 100 -> profit factor should be 3.0
    assert metrics["profit_factor"] == 3.0


def test_max_drawdown_calculation():
    results = _make_fake_backtest_results()
    metrics = calculate_metrics(results)

    # Peak was 10150, dropped to 10050 -> drawdown = (10150-10050)/10150 * 100
    expected_drawdown = round((10150 - 10050) / 10150 * 100, 2)
    assert metrics["max_drawdown_percent"] == expected_drawdown


def test_empty_trades_returns_safe_defaults():
    empty_results = {
        "closed_trades": [],
        "equity_curve": [{"timestamp": "2026-01-01", "balance": 10000}],
        "starting_balance": 10000,
        "ending_balance": 10000,
    }
    metrics = calculate_metrics(empty_results)
    assert metrics["number_of_trades"] == 0
    assert metrics["win_rate_percent"] is None


if __name__ == "__main__":
    test_basic_metrics_are_correct()
    test_profit_factor_calculation()
    test_max_drawdown_calculation()
    test_empty_trades_returns_safe_defaults()
    print("✅ All performance tests passed!")