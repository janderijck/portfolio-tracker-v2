from fastapi import APIRouter, HTTPException
from typing import List
from ..models import BrokerCreate, BrokerDetail, BrokerCashBalance, BrokerCashUpdate, BrokerAccountTypeUpdate, BrokerCashItem, CashSummary
from ..services.database import (
    get_db, get_available_brokers, get_broker_settings, get_broker_cash_balances,
    upsert_broker_cash_balance, update_broker_account_type,
)
from ..services.market_data import get_exchange_rate

router = APIRouter(prefix="/api", tags=["brokers"])


@router.get("/brokers", response_model=List[str])
async def get_brokers():
    """Get list of available brokers."""
    with get_db() as conn:
        return get_available_brokers(conn)


@router.post("/brokers")
async def create_broker(data: BrokerCreate):
    """Create a new broker."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO broker_settings (broker_name) VALUES (?)",
            (data.broker_name,)
        )
        conn.commit()
        return {"message": f"Broker {data.broker_name} created"}


@router.get("/brokers/details", response_model=List[BrokerDetail])
async def get_broker_details():
    """Get all brokers with their details including cash balances."""
    with get_db() as conn:
        brokers = get_broker_settings(conn)
        all_cash = get_broker_cash_balances(conn)

        # Group cash balances by broker
        cash_by_broker = {}
        for cb in all_cash:
            cash_by_broker.setdefault(cb['broker_name'], []).append(
                BrokerCashBalance(currency=cb['currency'], balance=cb['balance'])
            )

        return [
            BrokerDetail(
                broker_name=b['broker_name'],
                country=b.get('country', 'België'),
                has_w8ben=bool(b.get('has_w8ben', 0)),
                w8ben_expiry_date=b.get('w8ben_expiry_date'),
                cash_balances=cash_by_broker.get(b['broker_name'], []),
                account_type=b.get('account_type', 'Privé'),
                notes=b.get('notes'),
            )
            for b in brokers
        ]


@router.put("/brokers/{broker_name}/account-type")
async def update_broker_account_type_endpoint(broker_name: str, data: BrokerAccountTypeUpdate):
    """Update account type for a broker."""
    with get_db() as conn:
        broker = get_broker_settings(conn, broker_name)
        if not broker:
            raise HTTPException(status_code=404, detail=f"Broker {broker_name} not found")
        update_broker_account_type(conn, broker_name, data.account_type)
        return {"message": f"Account type voor {broker_name} bijgewerkt naar {data.account_type}"}


@router.put("/brokers/{broker_name}/cash")
async def update_broker_cash_endpoint(broker_name: str, data: BrokerCashUpdate):
    """Update cash balance for a broker (upsert; removes row if balance=0)."""
    with get_db() as conn:
        broker = get_broker_settings(conn, broker_name)
        if not broker:
            raise HTTPException(status_code=404, detail=f"Broker {broker_name} not found")
        upsert_broker_cash_balance(conn, broker_name, data.currency, data.balance)
        return {"message": f"Cash saldo voor {broker_name} ({data.currency}) bijgewerkt"}


@router.get("/brokers/cash-summary", response_model=CashSummary)
async def get_cash_summary():
    """Get total cash across all brokers in EUR."""
    with get_db() as conn:
        all_cash = get_broker_cash_balances(conn)
        per_broker = []
        total_cash_eur = 0.0

        for cb in all_cash:
            balance = cb['balance']
            currency = cb['currency']

            if balance == 0:
                continue

            if currency == 'EUR':
                cash_eur = balance
            else:
                rate = get_exchange_rate(currency, 'EUR')
                cash_eur = balance * rate

            per_broker.append(BrokerCashItem(
                broker_name=cb['broker_name'],
                cash_balance=balance,
                cash_currency=currency,
                cash_balance_eur=round(cash_eur, 2),
            ))
            total_cash_eur += cash_eur

        return CashSummary(
            total_cash_eur=round(total_cash_eur, 2),
            per_broker=per_broker,
        )
