from fastapi import APIRouter, HTTPException
from ..models import TelegramConfig, StockAlert, StockAlertCreate, AlertCheckResult
from ..services.database import (
    get_db, get_telegram_config, save_telegram_config, clear_telegram_config,
    get_alerts_for_stock, insert_alert, update_alert, delete_alert,
)

router = APIRouter(prefix="/api", tags=["telegram"])


@router.get("/telegram/config")
async def get_telegram_config_endpoint():
    """Get Telegram configuration."""
    with get_db() as conn:
        config = get_telegram_config(conn)
        return TelegramConfig(
            bot_token=config.get("bot_token", ""),
            chat_id=config.get("chat_id", ""),
        )


@router.put("/telegram/config")
async def save_telegram_config_endpoint(config: TelegramConfig):
    """Save Telegram configuration."""
    with get_db() as conn:
        save_telegram_config(conn, config.bot_token, config.chat_id)
        return config


@router.post("/telegram/test")
async def test_telegram():
    """Send a test message via Telegram."""
    from ..services.telegram import test_telegram_connection

    with get_db() as conn:
        config = get_telegram_config(conn)

    bot_token = config.get("bot_token", "")
    chat_id = config.get("chat_id", "")

    if not bot_token or not chat_id:
        raise HTTPException(status_code=400, detail="Telegram bot token en chat ID zijn vereist")

    result = test_telegram_connection(bot_token, chat_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/telegram/disconnect")
async def disconnect_telegram():
    """Clear Telegram configuration."""
    with get_db() as conn:
        clear_telegram_config(conn)
    return {"success": True, "message": "Telegram ontkoppeld"}


@router.get("/alerts/{ticker}")
async def get_stock_alerts(ticker: str):
    """Get all alerts for a stock."""
    with get_db() as conn:
        alerts = get_alerts_for_stock(conn, ticker)
        return [StockAlert(**a) for a in alerts]


@router.post("/alerts", response_model=StockAlert)
async def create_alert(alert: StockAlertCreate):
    """Create a new stock alert."""
    # Validate: period required for period alerts, threshold for price alerts
    if alert.alert_type in ("period_high", "period_low"):
        if not alert.period:
            raise HTTPException(
                status_code=400,
                detail="Periode is vereist voor period alerts (52w, 26w, 13w)"
            )
    elif alert.alert_type in ("above", "below"):
        if alert.threshold_price is None:
            raise HTTPException(
                status_code=400,
                detail="Drempelprijs is vereist voor prijs alerts"
            )

    with get_db() as conn:
        alert_id = insert_alert(conn, alert.model_dump())
        return StockAlert(id=alert_id, **alert.model_dump())


@router.put("/alerts/{alert_id}", response_model=StockAlert)
async def update_alert_endpoint(alert_id: int, alert: StockAlertCreate):
    """Update an existing alert."""
    with get_db() as conn:
        if not update_alert(conn, alert_id, alert.model_dump()):
            raise HTTPException(status_code=404, detail="Alert niet gevonden")
        return StockAlert(id=alert_id, **alert.model_dump())


@router.delete("/alerts/{alert_id}")
async def delete_alert_endpoint(alert_id: int):
    """Delete an alert."""
    with get_db() as conn:
        if delete_alert(conn, alert_id):
            return {"message": "Alert verwijderd"}
        raise HTTPException(status_code=404, detail="Alert niet gevonden")


@router.post("/alerts/check", response_model=AlertCheckResult)
async def manual_check_alerts():
    """Manually trigger an alert check (for testing)."""
    from ..services.alert_checker import check_all_alerts

    result = check_all_alerts()
    return AlertCheckResult(**result)
