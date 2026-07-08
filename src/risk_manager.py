"""
risk_manager.py
Purpose: Enforce strict risk management rules before any trade is allowed.
         This is the bot's survival layer — it can override a strategy
         signal, but a strategy signal can never override risk rules.
"""

from datetime import datetime, timedelta

# --- Risk configuration (matches our Phase 7 rulebook) ---
MAX_RISK_PER_TRADE_PERCENT = 1.0
MAX_DAILY_LOSS_PERCENT = 3.0
MAX_WEEKLY_LOSS_PERCENT = 6.0
MAX_TOTAL_DRAWDOWN_PERCENT = 15.0
MAX_TRADES_PER_DAY = 3
MAX_CONSECUTIVE_LOSSES = 4
MIN_RISK_REWARD_RATIO = 1.5
MIN_ACCOUNT_BALANCE = 1_000.0
MAX_SPREAD_PIPS = 2.0
MIN_CONFIDENCE_SCORE = 60

PIP_SIZE = 0.0001  # EUR/USD and most major pairs


class RiskManager:
    """
    Tracks account state over time (balance history, daily/weekly loss,
    consecutive losses, peak balance) and validates every proposed trade
    against our risk rules before allowing it.
    """

    def __init__(self, starting_balance):
        self.starting_balance = starting_balance
        self.current_balance = starting_balance
        self.peak_balance = starting_balance

        self.kill_switch_active = False
        self.kill_switch_reason = None

        self.consecutive_losses = 0

        self.trades_today = 0
        self.loss_today = 0.0
        self.current_day = None

        self.loss_this_week = 0.0
        self.current_week = None

    # --- Public method: call this before every proposed trade ---
    def validate_trade(self, decision, current_timestamp, spread_pips=None):
        """
        decision: the trade decision dict from strategy.generate_signal()
                  (must include entry_price, stop_loss, risk_reward_ratio,
                  confidence_score).
        current_timestamp: the timestamp of the candle being evaluated.
        spread_pips: current spread, if available.

        Returns the standard trade approval dictionary.
        """
        self._roll_day_and_week_if_needed(current_timestamp)

        rejection_reasons = []
        warnings = []

        # --- Kill switch check (always first — overrides everything) ---
        if self.kill_switch_active:
            rejection_reasons.append(f"Kill switch active: {self.kill_switch_reason}")
            return self._build_response(False, None, None, rejection_reasons, warnings)

        # --- Minimum account balance check ---
        if self.current_balance < MIN_ACCOUNT_BALANCE:
            rejection_reasons.append(
                f"Balance (${self.current_balance:.2f}) below minimum required "
                f"(${MIN_ACCOUNT_BALANCE:.2f})."
            )

        # --- Confidence score check ---
        if decision.get("confidence_score", 0) < MIN_CONFIDENCE_SCORE:
            rejection_reasons.append(
                f"Confidence score ({decision.get('confidence_score', 0)}) below "
                f"minimum ({MIN_CONFIDENCE_SCORE})."
            )

        # --- Risk/reward check ---
        if decision.get("risk_reward_ratio", 0) < MIN_RISK_REWARD_RATIO:
            rejection_reasons.append(
                f"Risk/reward ({decision.get('risk_reward_ratio', 0)}) below "
                f"minimum ({MIN_RISK_REWARD_RATIO})."
            )

        # --- Spread check ---
        if spread_pips is not None and spread_pips > MAX_SPREAD_PIPS:
            rejection_reasons.append(f"Spread ({spread_pips} pips) too high.")

        # --- Daily trade count check ---
        if self.trades_today >= MAX_TRADES_PER_DAY:
            rejection_reasons.append(
                f"Maximum trades per day ({MAX_TRADES_PER_DAY}) already reached."
            )

        # --- Consecutive losses check ---
        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            rejection_reasons.append(
                f"Consecutive losses ({self.consecutive_losses}) reached limit "
                f"({MAX_CONSECUTIVE_LOSSES}) — cooldown required."
            )

        # --- Daily loss limit check ---
        max_daily_loss_dollars = self.starting_balance * (MAX_DAILY_LOSS_PERCENT / 100)
        if self.loss_today >= max_daily_loss_dollars:
            rejection_reasons.append(
                f"Daily loss limit reached (${self.loss_today:.2f} of "
                f"${max_daily_loss_dollars:.2f})."
            )

        # --- Weekly loss limit check ---
        max_weekly_loss_dollars = self.starting_balance * (MAX_WEEKLY_LOSS_PERCENT / 100)
        if self.loss_this_week >= max_weekly_loss_dollars:
            rejection_reasons.append(
                f"Weekly loss limit reached (${self.loss_this_week:.2f} of "
                f"${max_weekly_loss_dollars:.2f})."
            )

        # --- Total drawdown check (triggers kill switch, not just rejection) ---
        drawdown_percent = self._current_drawdown_percent()
        if drawdown_percent >= MAX_TOTAL_DRAWDOWN_PERCENT:
            self._activate_kill_switch(
                f"Maximum drawdown reached ({drawdown_percent:.2f}%)."
            )
            rejection_reasons.append(f"Kill switch triggered: {self.kill_switch_reason}")

        # If anything failed, reject now before calculating position size
        if rejection_reasons:
            return self._build_response(False, None, None, rejection_reasons, warnings)

        # --- Calculate position size ---
        sizing = calculate_position_size(
            account_balance=self.current_balance,
            risk_percent=MAX_RISK_PER_TRADE_PERCENT,
            entry_price=decision["entry_price"],
            stop_loss_price=decision["stop_loss"],
        )

        if sizing["warning"]:
            warnings.append(sizing["warning"])

        return self._build_response(
            True, sizing["position_size"], sizing["risk_amount"], rejection_reasons, warnings
        )

    # --- Call this after a trade closes, to update tracking ---
    def record_trade_result(self, pnl_dollars, exit_timestamp):
        self._roll_day_and_week_if_needed(exit_timestamp)

        self.current_balance += pnl_dollars
        self.peak_balance = max(self.peak_balance, self.current_balance)

        self.trades_today += 1

        if pnl_dollars < 0:
            self.loss_today += abs(pnl_dollars)
            self.loss_this_week += abs(pnl_dollars)
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        # Re-check drawdown after updating balance
        drawdown_percent = self._current_drawdown_percent()
        if drawdown_percent >= MAX_TOTAL_DRAWDOWN_PERCENT and not self.kill_switch_active:
            self._activate_kill_switch(
                f"Maximum drawdown reached ({drawdown_percent:.2f}%) after trade close."
            )

    def reset_kill_switch(self):
        """Manually reset the kill switch — a deliberate human decision, never automatic."""
        self.kill_switch_active = False
        self.kill_switch_reason = None

    # --- Internal helpers ---
    def _activate_kill_switch(self, reason):
        self.kill_switch_active = True
        self.kill_switch_reason = reason

    def _current_drawdown_percent(self):
        if self.peak_balance == 0:
            return 0
        return ((self.peak_balance - self.current_balance) / self.peak_balance) * 100

    def _roll_day_and_week_if_needed(self, timestamp):
        ts = _as_datetime(timestamp)
        day_key = ts.date()
        week_key = ts.isocalendar()[:2]  # (year, week number)

        if self.current_day != day_key:
            self.current_day = day_key
            self.trades_today = 0
            self.loss_today = 0.0

        if self.current_week != week_key:
            self.current_week = week_key
            self.loss_this_week = 0.0

    def _build_response(self, approved, position_size, risk_amount, rejection_reasons, warnings):
        return {
            "approved": approved,
            "position_size": position_size,
            "risk_amount": risk_amount,
            "rejection_reasons": rejection_reasons,
            "warnings": warnings,
            "active_limits": {
                "trades_today": self.trades_today,
                "max_trades_per_day": MAX_TRADES_PER_DAY,
                "loss_today": round(self.loss_today, 2),
                "max_daily_loss_dollars": round(
                    self.starting_balance * (MAX_DAILY_LOSS_PERCENT / 100), 2
                ),
                "loss_this_week": round(self.loss_this_week, 2),
                "max_weekly_loss_dollars": round(
                    self.starting_balance * (MAX_WEEKLY_LOSS_PERCENT / 100), 2
                ),
                "consecutive_losses": self.consecutive_losses,
                "max_consecutive_losses": MAX_CONSECUTIVE_LOSSES,
                "current_drawdown_percent": round(self._current_drawdown_percent(), 2),
                "max_drawdown_percent": MAX_TOTAL_DRAWDOWN_PERCENT,
                "current_balance": round(self.current_balance, 2),
            },
            "kill_switch_status": "ACTIVE" if self.kill_switch_active else "INACTIVE",
        }


def _as_datetime(timestamp):
    """Handles both pandas Timestamps and plain datetimes safely."""
    if hasattr(timestamp, "to_pydatetime"):
        return timestamp.to_pydatetime()
    return timestamp


def calculate_position_size(account_balance, risk_percent, entry_price, stop_loss_price):
    """
    Calculates how large a position should be so that hitting the stop
    loss loses exactly `risk_percent` of the account — no more.

    Returns: position_size (in units), risk_amount (dollars),
             stop_distance (price difference), and an optional warning.
    """
    risk_amount = account_balance * (risk_percent / 100)
    stop_distance = abs(entry_price - stop_loss_price)

    warning = None

    if stop_distance <= 0:
        return {
            "position_size": 0,
            "risk_amount": risk_amount,
            "stop_distance": stop_distance,
            "warning": "Stop distance is zero or invalid — cannot size position.",
        }

    # Position size in "units" of the base currency such that:
    # position_size * stop_distance = risk_amount
    position_size = risk_amount / stop_distance

    # Sanity check: flag unusually large positions (a common sign that
    # a stop loss was placed too close, or risk % is set too high)
    if position_size > account_balance * 50:
        warning = (
            "Calculated position size is unusually large relative to account "
            "balance — check that stop loss distance is realistic."
        )

    return {
        "position_size": round(position_size, 2),
        "risk_amount": round(risk_amount, 2),
        "stop_distance": round(stop_distance, 5),
        "warning": warning,
    }