"""
Telegram Bot API integration for price alerts.
"""
import logging
import requests

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


def send_telegram_message(bot_token: str, chat_id: str, message: str) -> bool:
    """Send a message via Telegram Bot API. Returns True on success."""
    url = f"{TELEGRAM_API_BASE.format(token=bot_token)}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


def test_telegram_connection(bot_token: str, chat_id: str) -> dict:
    """Send a test message and return result."""
    message = (
        "<b>Portfolio Tracker - Testbericht</b>\n\n"
        "Telegram koppeling werkt correct! "
        "Je ontvangt hier prijsalerts voor je aandelen."
    )
    success = send_telegram_message(bot_token, chat_id, message)
    if success:
        return {"success": True, "message": "Testbericht verzonden!"}
    return {"success": False, "message": "Kon geen bericht sturen. Controleer bot token en chat ID."}


def format_alert_message(
    ticker: str,
    stock_name: str,
    alert_type: str,
    current_price: float,
    currency: str,
    period: str = None,
    threshold_price: float = None,
    period_high: float = None,
    period_low: float = None,
) -> str:
    """Format a price alert as an HTML Telegram message."""
    currency_symbol = "€" if currency == "EUR" else "$" if currency == "USD" else currency

    if alert_type == "period_high":
        period_label = _period_label(period)
        return (
            f"<b>{ticker}</b> - {stock_name}\n\n"
            f"Nieuw {period_label} hoog!\n"
            f"Huidige koers: {currency_symbol}{current_price:.2f}\n"
            f"Vorig hoog: {currency_symbol}{period_high:.2f}"
        )
    elif alert_type == "period_low":
        period_label = _period_label(period)
        return (
            f"<b>{ticker}</b> - {stock_name}\n\n"
            f"Nieuw {period_label} laag!\n"
            f"Huidige koers: {currency_symbol}{current_price:.2f}\n"
            f"Vorig laag: {currency_symbol}{period_low:.2f}"
        )
    elif alert_type == "above":
        return (
            f"<b>{ticker}</b> - {stock_name}\n\n"
            f"Koers boven drempel!\n"
            f"Huidige koers: {currency_symbol}{current_price:.2f}\n"
            f"Drempel: {currency_symbol}{threshold_price:.2f}"
        )
    elif alert_type == "below":
        return (
            f"<b>{ticker}</b> - {stock_name}\n\n"
            f"Koers onder drempel!\n"
            f"Huidige koers: {currency_symbol}{current_price:.2f}\n"
            f"Drempel: {currency_symbol}{threshold_price:.2f}"
        )
    else:
        return f"<b>{ticker}</b> - Alert getriggerd (type: {alert_type})"


def _period_label(period: str) -> str:
    """Convert period code to human-readable label."""
    labels = {
        "52w": "52-week",
        "26w": "26-week",
        "13w": "13-week",
    }
    return labels.get(period, period or "periode")
