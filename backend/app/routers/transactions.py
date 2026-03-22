from fastapi import APIRouter, HTTPException
from typing import List, Optional
from ..models import Transaction, TransactionCreate
from ..services.database import get_db, get_all_transactions, insert_transaction, update_transaction, delete_transaction

router = APIRouter(prefix="/api", tags=["transactions"])


@router.get("/transactions", response_model=List[Transaction])
async def get_transactions(ticker: Optional[str] = None):
    """Get all transactions, optionally filtered by ticker."""
    with get_db() as conn:
        transactions = get_all_transactions(conn, ticker)
        return [Transaction(**tx) for tx in transactions]


@router.post("/transactions", response_model=Transaction)
async def create_transaction(transaction: TransactionCreate):
    """Create a new transaction."""
    with get_db() as conn:
        tx_id = insert_transaction(conn, transaction.model_dump())
        return Transaction(id=tx_id, **transaction.model_dump())


@router.put("/transactions/{transaction_id}", response_model=Transaction)
async def edit_transaction(transaction_id: int, transaction: TransactionCreate):
    """Update a transaction."""
    with get_db() as conn:
        if not update_transaction(conn, transaction_id, transaction.model_dump()):
            raise HTTPException(status_code=404, detail="Transaction not found")
        return Transaction(id=transaction_id, **transaction.model_dump())


@router.delete("/transactions/{transaction_id}")
async def remove_transaction(transaction_id: int):
    """Delete a transaction."""
    with get_db() as conn:
        if delete_transaction(conn, transaction_id):
            return {"message": "Transaction deleted"}
        raise HTTPException(status_code=404, detail="Transaction not found")
