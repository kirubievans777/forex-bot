"""
demo_executor.py
Purpose: The safety gatekeeper between a strategy decision and an
         actual demo broker order. Runs the full safety checklist
         before allowing ANY order to be placed.
"""

from logger import log_trade, log_error
from datetime import datetime, timezone

ALLOWED_PAIRS = ["EUR/USD"]
MAX_SPREAD_PIPS = 2.0
MAX_REASONABLE_POSITION_SIZE = 1_000_000  # sanity ceiling, not a real limit


class DemoTradeExecutor:
    """
    Coordinates between a strategy decision, the risk manager, and a
    broker connection — enforcing every safety check before any order
    is placed. Refuses to operate against anything but a demo account.
    """

    def __init__(self, broker, risk_manager, strategy_version="v1"):
        self.broker = broker
        self.risk_manager = risk_manager
        self.strategy_version = strategy_version

        # Hard safety check: refuse to even initialize against a live account
        account_info = self.broker.get_account_info()
        if account_info.get("mode") != "demo":
            raise ValueError(
                "SAFETY STOP: Broker account mode is not 'demo'. "
                "DemoTradeExecutor refuses to operate against a non-demo account."
            )

    def execute_decision(self, decision, current_timestamp=None):
        """
        Takes a strategy decision dictionary, runs the full safety
        checklist, and places a demo order only if every check passes.

        Returns a result dictionary describing what happened.
        """
        current_timestamp = current_timestamp or datetime.now(timezone.utc)
        checklist_failures = []

        # --- Check 1: Strategy signal is valid ---
        if decision.get("signal") not in ("BUY", "SELL"):
            checklist_failures.append("Strategy signal is not BUY or SELL.")
            return self._reject(checklist_failures)

        pair = "EUR/USD"  # Fixed for Version 1

        # --- Check 2: Risk manager approves the trade ---
        risk_result = self.risk_manager.validate_trade(decision, current_timestamp)
        if not risk_result["approved"]:
            checklist_failures.extend(risk_result["rejection_reasons"])
            return self._reject(checklist_failures)

        # --- Check 3: Account mode is demo (re-confirmed every time) ---
        account_info = self.broker.get_account_info()
        if account_info.get("mode") != "demo":
            checklist_failures.append("Account mode is not demo — refusing to trade.")
            return self._reject(checklist_failures)

        # --- Check 4: Pair is allowed ---
        if pair not in ALLOWED_PAIRS:
            checklist_failures.append(f"Pair {pair} is not in the allowed list.")
            return self._reject(checklist_failures)

        # --- Check 5: Position size is valid ---
        position_size = risk_result["position_size"]
        if not position_size or position_size <= 0:
            checklist_failures.append("Position size is invalid (zero or negative).")
            return self._reject(checklist_failures)
        if position_size > MAX_REASONABLE_POSITION_SIZE:
            checklist_failures.append("Position size is unreasonably large — safety ceiling exceeded.")
            return self._reject(checklist_failures)

        # --- Check 6 & 7: Stop loss and take profit exist ---
        if not decision.get("stop_loss"):
            checklist_failures.append("Stop loss is missing.")
        if not decision.get("take_profit"):
            checklist_failures.append("Take profit is missing.")
        if checklist_failures:
            return self._reject(checklist_failures)

        # --- Check 8: Max trades per day (already enforced by risk_manager,
        #     re-confirmed here for defense-in-depth) ---
        active_limits = risk_result["active_limits"]
        if active_limits["trades_today"] >= active_limits["max_trades_per_day"]:
            checklist_failures.append("Maximum trades per day already reached.")
            return self._reject(checklist_failures)

        # --- Check 9: Kill switch not active ---
        if risk_result["kill_switch_status"] == "ACTIVE":
            checklist_failures.append("Kill switch is active — no trades permitted.")
            return self._reject(checklist_failures)

        # --- Check 10: Spread is acceptable ---
        price_info = self.broker.get_latest_price(pair)
        if price_info["spread_pips"] > MAX_SPREAD_PIPS:
            checklist_failures.append(
                f"Spread too high ({price_info['spread_pips']} pips)."
            )
            return self._reject(checklist_failures)

        # --- Check 11: No duplicate open trade for this pair ---
        open_positions = self.broker.get_open_positions()
        for position in open_positions:
            position_pair = position.get("pair") or position.get("instrument", "").replace("_", "/")
            if position_pair == pair:
                checklist_failures.append(f"A trade is already open for {pair}.")
                return self._reject(checklist_failures)

        # --- All checks passed: place the order ---
        try:
            order_result = self.broker.place_order(
                pair=pair,
                direction=decision["signal"],
                units=position_size,
                stop_loss=decision["stop_loss"],
                take_profit=decision["take_profit"],
            )
        except Exception as e:
            log_error(
                error_type="OrderPlacementError",
                error_message=str(e),
                file="demo_executor.py",
                function="execute_decision",
                severity="HIGH",
                action_taken="Order not placed, error logged.",
            )
            return {
                "executed": False,
                "reason": f"Order placement failed: {e}",
            }

        # --- Log the trade ---
        log_trade({
            "trade_id": order_result.get("order_id", "UNKNOWN"),
            "entry_time": current_timestamp,
            "pair": pair,
            "direction": decision["signal"],
            "entry_price": decision["entry_price"],
            "stop_loss": decision["stop_loss"],
            "take_profit": decision["take_profit"],
            "position_size": position_size,
            "risk_amount": risk_result["risk_amount"],
            "risk_reward_planned": decision["risk_reward_ratio"],
            "strategy_version": self.strategy_version,
            "notes": "Opened via DemoTradeExecutor",
        })

        return {
            "executed": True,
            "order_result": order_result,
            "position_size": position_size,
            "risk_amount": risk_result["risk_amount"],
        }

    def _reject(self, reasons):
        """Builds a standard rejection response and logs it."""
        return {
            "executed": False,
            "reasons": reasons,
        }