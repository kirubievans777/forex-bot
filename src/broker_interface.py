"""
broker_interface.py
Purpose: Defines a common structure ("interface") that any broker
         connection must follow, plus two implementations:
         - MockBroker: a safe, fake broker for testing without any
           real connection (used heavily in our tests).
         - MT5DemoBroker: a real connection to a MetaTrader 5 demo
           account, using the locally running MT5 terminal.

IMPORTANT: This file only ever connects to DEMO accounts. The
MT5DemoBroker class refuses to initialize against anything else.
"""

from abc import ABC, abstractmethod


class BrokerInterface(ABC):
    """
    Abstract base class — defines what every broker connection must
    be able to do. Any real or mock broker we build must implement
    all of these methods.
    """

    @abstractmethod
    def get_account_info(self):
        """Returns account balance, currency, and mode (demo/live)."""
        pass

    @abstractmethod
    def get_latest_price(self, pair):
        """Returns the latest bid/ask price and spread for a pair."""
        pass

    @abstractmethod
    def get_open_positions(self):
        """Returns a list of currently open positions."""
        pass

    @abstractmethod
    def place_order(self, pair, direction, units, stop_loss, take_profit):
        """Places a market order with stop loss and take profit."""
        pass

    @abstractmethod
    def close_order(self, pair):
        """Closes any open position for the given pair."""
        pass

    @abstractmethod
    def get_order_status(self, order_id):
        """Returns the current status of a specific order."""
        pass


class MockBroker(BrokerInterface):
    """
    A safe, fully fake broker used for testing our executor logic
    without needing any real connection or credentials.
    Behaves predictably so we can write reliable tests against it.
    """

    def __init__(self, starting_balance=100_000.0, mode="demo"):
        self.balance = starting_balance
        self.mode = mode
        self.open_positions = {}  # pair -> position dict
        self.next_order_id = 1
        self.simulated_spread_pips = 1.2
        self.simulated_price = 1.1000

    def get_account_info(self):
        return {
            "balance": self.balance,
            "currency": "USD",
            "mode": self.mode,
        }

    def get_latest_price(self, pair):
        return {
            "pair": pair,
            "bid": round(self.simulated_price - 0.00006, 5),
            "ask": round(self.simulated_price + 0.00006, 5),
            "spread_pips": self.simulated_spread_pips,
        }

    def get_open_positions(self):
        return list(self.open_positions.values())

    def place_order(self, pair, direction, units, stop_loss, take_profit):
        order_id = f"MOCK-{self.next_order_id}"
        self.next_order_id += 1

        position = {
            "order_id": order_id,
            "pair": pair,
            "direction": direction,
            "units": units,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "status": "FILLED",
        }
        self.open_positions[pair] = position
        return position

    def close_order(self, pair):
        if pair in self.open_positions:
            closed = self.open_positions.pop(pair)
            closed["status"] = "CLOSED"
            return closed
        return {"status": "NO_POSITION_FOUND"}

    def get_order_status(self, order_id):
        for position in self.open_positions.values():
            if position["order_id"] == order_id:
                return position["status"]
        return "UNKNOWN"


class MT5DemoBroker(BrokerInterface):
    """
    Real connection to a MetaTrader 5 demo account via the official
    MetaTrader5 Python package. Requires the MT5 terminal to be
    installed, running, and logged into a DEMO account.
    """

    def __init__(self, symbol="EURUSD"):
        import MetaTrader5 as mt5
        self.mt5 = mt5
        self.symbol = symbol

        if not self.mt5.initialize():
            raise ConnectionError(
                f"Failed to connect to MT5 terminal: {self.mt5.last_error()}"
            )

        account_info = self.mt5.account_info()
        if account_info is None:
            raise ConnectionError("Could not retrieve MT5 account info.")

        # Safety check: MT5 account_info().trade_mode == 0 means DEMO.
        # 1 = contest, 2 = real. We refuse anything that isn't demo.
        if account_info.trade_mode != 0:
            self.mt5.shutdown()
            raise ValueError(
                "SAFETY STOP: Connected MT5 account is not a demo account "
                "(trade_mode != DEMO). Refusing to proceed."
            )

        self.mode = "demo"

    def get_account_info(self):
        info = self.mt5.account_info()
        return {"balance": info.balance, "currency": info.currency, "mode": "demo"}

    def get_latest_price(self, pair):
        tick = self.mt5.symbol_info_tick(self.symbol)
        spread_pips = round((tick.ask - tick.bid) * 10_000, 1)
        return {"pair": pair, "bid": tick.bid, "ask": tick.ask, "spread_pips": spread_pips}

    def get_open_positions(self):
        positions = self.mt5.positions_get(symbol=self.symbol)
        return [
            {"pair": self.symbol, "ticket": p.ticket, "type": p.type, "volume": p.volume}
            for p in (positions or [])
        ]

    def place_order(self, pair, direction, units, stop_loss, take_profit):
        order_type = self.mt5.ORDER_TYPE_BUY if direction == "BUY" else self.mt5.ORDER_TYPE_SELL
        tick = self.mt5.symbol_info_tick(self.symbol)
        price = tick.ask if direction == "BUY" else tick.bid

        # MT5 volume is in "lots", not raw units — 1 standard lot = 100,000 units
        volume_lots = round(units / 100_000, 2)

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": max(volume_lots, 0.01),  # MT5 minimum is typically 0.01 lots
            "type": order_type,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "type_filling": self.mt5.ORDER_FILLING_IOC,
        }
        result = self.mt5.order_send(request)

        if result.retcode != self.mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"MT5 order failed: {result.comment}")

        return {"order_id": result.order, "status": "FILLED"}

    def close_order(self, pair):
        positions = self.mt5.positions_get(symbol=self.symbol)
        if not positions:
            return {"status": "NO_POSITION_FOUND"}

        position = positions[0]
        close_type = (
            self.mt5.ORDER_TYPE_SELL if position.type == self.mt5.ORDER_TYPE_BUY
            else self.mt5.ORDER_TYPE_BUY
        )
        tick = self.mt5.symbol_info_tick(self.symbol)
        price = tick.bid if close_type == self.mt5.ORDER_TYPE_SELL else tick.ask

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": position.volume,
            "type": close_type,
            "position": position.ticket,
            "price": price,
            "type_filling": self.mt5.ORDER_FILLING_IOC,
        }
        result = self.mt5.order_send(request)
        return {"status": "CLOSED" if result.retcode == self.mt5.TRADE_RETCODE_DONE else "FAILED"}

    def get_order_status(self, order_id):
        orders = self.mt5.history_orders_get(ticket=order_id)
        if orders:
            return "FILLED"
        return "UNKNOWN"