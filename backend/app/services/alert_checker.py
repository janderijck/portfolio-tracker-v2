"""
Alert checker service - checks all enabled alerts and sends Telegram notifications.

Called hourly by the scheduler. Max 1 alert per alert per 24 hours.
"""
import logging
from datetime import datetime, timedelta

import yfinance as yf

from .database import (
    get_db, get_telegram_config, get_all_enabled_alerts,
    get_stock_info, update_alert_triggered,
)
from .market_data import get_cached_price_only
from .telegram import send_telegram_message, format_alert_message

logger = logging.getLogger(__name__)

PERIOD_DAYS = {
    "52w": 365,
    "26w": 182,
    "13w": 91,
}


def check_all_alerts() -> dict:
    """Main function: check all enabled alerts against current prices.

    Returns dict with checked/triggered/errors counts.
    """
    result = {"checked": 0, "triggered": 0, "errors": []}

    try:
        with get_db() as conn:
            telegram_config = get_telegram_config(conn)
            bot_token = telegram_config.get("bot_token", "")
            chat_id = telegram_config.get("chat_id", "")

            if not bot_token or not chat_id:
                logger.info("Alert check skipped: no Telegram config")
                return result

            alerts = get_all_enabled_alerts(conn)
            if not alerts:
                return result

            for alert in alerts:
                result["checked"] += 1
                try:
                    if not _should_send_alert(alert.get("last_triggered_at")):
                        continue

                    triggered = _check_single_alert(conn, alert, bot_token, chat_id)
                    if triggered:
                        result["triggered"] += 1
                except Exception as e:
                    error_msg = f"Alert {alert['id']} ({alert['ticker']}): {str(e)}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)

    except Exception as e:
        logger.error(f"Alert checker failed: {e}")
        result["errors"].append(str(e))

    logger.info(
        f"Alert check done: {result['checked']} checked, "
        f"{result['triggered']} triggered, {len(result['errors'])} errors"
    )
    return result


def _check_single_alert(conn, alert: dict, bot_token: str, chat_id: str) -> bool:
    """Check a single alert. Returns True if triggered."""
    ticker = alert["ticker"]
    alert_type = alert["alert_type"]

    stock_info = get_stock_info(conn, ticker)
    stock_name = stock_info["name"] if stock_info else ticker
    yahoo_ticker = (stock_info.get("yahoo_ticker") or ticker) if stock_info else ticker

    # Get current price from cache
    price_info = get_cached_price_only(yahoo_ticker)
    if not price_info or not price_info.get("current_price"):
        return False

    current_price = price_info["current_price"]
    currency = price_info.get("currency", "USD")

    triggered = False
    msg_kwargs = {
        "ticker": ticker,
        "stock_name": stock_name,
        "alert_type": alert_type,
        "current_price": current_price,
        "currency": currency,
    }

    if alert_type in ("period_high", "period_low"):
        period = alert.get("period", "52w")
        days = PERIOD_DAYS.get(period, 365)
        high, low = _get_period_high_low(yahoo_ticker, days)

        if high is None or low is None:
            return False

        msg_kwargs["period"] = period
        msg_kwargs["period_high"] = high
        msg_kwargs["period_low"] = low

        if alert_type == "period_high" and current_price >= high:
            triggered = True
        elif alert_type == "period_low" and current_price <= low:
            triggered = True

    elif alert_type == "above":
        threshold = alert.get("threshold_price")
        if threshold and current_price >= threshold:
            triggered = True
            msg_kwargs["threshold_price"] = threshold

    elif alert_type == "below":
        threshold = alert.get("threshold_price")
        if threshold and current_price <= threshold:
            triggered = True
            msg_kwargs["threshold_price"] = threshold

    if triggered:
        message = format_alert_message(**msg_kwargs)
        success = send_telegram_message(bot_token, chat_id, message)
        if success:
            update_alert_triggered(conn, alert["id"])
            return True
        else:
            logger.warning(f"Failed to send Telegram for alert {alert['id']}")

    return False


def _get_period_high_low(yahoo_ticker: str, days: int) -> tuple:
    """Get the high and low prices for a period via yfinance.

    Returns (high, low) or (None, None) on failure.
    """
    try:
        stock = yf.Ticker(yahoo_ticker)
        hist = stock.history(period=f"{days}d")
        if hist.empty:
            return None, None
        high = float(hist["High"].max())
        low = float(hist["Low"].min())
        return high, low
    except Exception as e:
        logger.error(f"Failed to get period high/low for {yahoo_ticker}: {e}")
        return None, None


def _should_send_alert(last_triggered_at: str | None) -> bool:
    """Check if at least 24 hours have passed since last trigger."""
    if not last_triggered_at:
        return True
    try:
        last = datetime.fromisoformat(last_triggered_at)
        return datetime.now() - last > timedelta(hours=24)
    except (ValueError, TypeError):
        return True
