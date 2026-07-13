"""
test_broker_interface.py
Purpose: Confirm MockBroker behaves correctly and safely, since our
         other tests depend on it behaving predictably.
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from broker_interface import MockBroker


def test_mock_broker_starts_in_demo_mode():
    broker = MockBroker()
    info = broker.get_account_info()
    assert info["mode"] == "demo"


def test_mock_broker_get_latest_price_has_spread():
    broker = MockBroker()
    price = broker.get_latest_price("EUR/USD")
    assert price["ask"] > price["bid"]
    assert price["spread_pips"] > 0


def test_mock_broker_place_and_retrieve_order():
    broker = MockBroker()
    result = broker.place_order(
        pair="EUR/USD", direction="BUY", units=1000,
        stop_loss=1.0950, take_profit=1.1100,
    )
    assert result["status"] == "FILLED"

    open_positions = broker.get_open_positions()
    assert len(open_positions) == 1
    assert open_positions[0]["pair"] == "EUR/USD"


def test_mock_broker_close_order():
    broker = MockBroker()
    broker.place_order(
        pair="EUR/USD", direction="BUY", units=1000,
        stop_loss=1.0950, take_profit=1.1100,
    )
    closed = broker.close_order("EUR/USD")
    assert closed["status"] == "CLOSED"
    assert len(broker.get_open_positions()) == 0


def test_mock_broker_close_nonexistent_order():
    broker = MockBroker()
    result = broker.close_order("EUR/USD")
    assert result["status"] == "NO_POSITION_FOUND"


if __name__ == "__main__":
    test_mock_broker_starts_in_demo_mode()
    test_mock_broker_get_latest_price_has_spread()
    test_mock_broker_place_and_retrieve_order()
    test_mock_broker_close_order()
    test_mock_broker_close_nonexistent_order()
    print("✅ All broker interface tests passed!")