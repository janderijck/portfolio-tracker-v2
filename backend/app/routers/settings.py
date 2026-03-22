from fastapi import APIRouter, HTTPException
from ..models import UserSettings
from ..services.database import get_db, get_user_settings, update_user_settings, clear_all_data

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings", response_model=UserSettings)
async def get_settings():
    """Get user settings."""
    with get_db() as conn:
        settings = get_user_settings(conn)
        saxo_token = settings.get('saxo_access_token')
        return UserSettings(
            date_format=settings.get('date_format', 'DD/MM/YYYY'),
            finnhub_api_key=settings.get('finnhub_api_key'),
            openfigi_api_key=settings.get('openfigi_api_key'),
            saxo_connected=bool(saxo_token),
        )


@router.put("/settings", response_model=UserSettings)
async def save_settings(settings: UserSettings):
    """Update user settings."""
    with get_db() as conn:
        # Only update non-Saxo settings (Saxo tokens managed via OAuth)
        update_user_settings(conn, {
            'date_format': settings.date_format,
            'finnhub_api_key': settings.finnhub_api_key,
            'openfigi_api_key': settings.openfigi_api_key,
        })
        return settings


@router.delete("/database/reset")
async def reset_database():
    """Delete all data (transactions, dividends, stocks, caches) but keep settings and brokers."""
    with get_db() as conn:
        clear_all_data(conn)
        return {"message": "Alle gegevens zijn gewist"}


@router.post("/settings/test-finnhub")
async def test_finnhub_api():
    """Test Finnhub API connection by doing a simple quote lookup."""
    from ..services.market_data import _get_finnhub_client

    client = _get_finnhub_client()
    if not client:
        raise HTTPException(status_code=400, detail="Geen Finnhub API key ingesteld")

    try:
        # Test with a simple quote lookup for Apple
        quote = client.quote('AAPL')
        if quote and quote.get('c'):
            return {
                "success": True,
                "message": "Finnhub API werkt correct!",
                "test_data": {
                    "ticker": "AAPL",
                    "price": quote.get('c'),
                    "change_percent": quote.get('dp')
                }
            }
        else:
            raise HTTPException(status_code=400, detail="Finnhub API antwoordde, maar data is ongeldig")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Finnhub API test mislukt: {str(e)}")
