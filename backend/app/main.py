"""
Portfolio Tracker API - Main application.

Routes are organized in separate router modules under app/routers/.
"""
import logging
import os
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .routers import (
    portfolio,
    transactions,
    dividends,
    stocks,
    brokers,
    analysis,
    settings,
    saxo,
    ibkr,
    imports,
    telegram,
)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle: start and stop the alert scheduler."""
    from .services.alert_checker import check_all_alerts

    scheduler.add_job(check_all_alerts, "interval", hours=1, id="alert_checker")
    scheduler.start()
    logging.getLogger(__name__).info("Alert scheduler started (interval: 1 hour)")
    yield
    scheduler.shutdown()


app = FastAPI(
    title="Portfolio Tracker API",
    description="API for tracking stock portfolio and dividends",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware
frontend_url = os.getenv("FRONTEND_URL", "")
cors_regex = os.getenv("CORS_ORIGIN_REGEX", "")
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:5177",
    "http://localhost:3000",
    "http://localhost:8080",
]

if frontend_url:
    allowed_origins.append(frontend_url)

cors_kwargs: dict = {
    "allow_origins": allowed_origins,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if cors_regex:
    cors_kwargs["allow_origin_regex"] = cors_regex

app.add_middleware(CORSMiddleware, **cors_kwargs)


# Register routers
app.include_router(portfolio.router)
app.include_router(transactions.router)
app.include_router(dividends.router)
app.include_router(stocks.router)
app.include_router(brokers.router)
app.include_router(analysis.router)
app.include_router(settings.router)
app.include_router(saxo.router)
app.include_router(ibkr.router)
app.include_router(imports.router)
app.include_router(telegram.router)


@app.get("/")
async def root():
    return {"message": "Portfolio Tracker API v2", "status": "running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
