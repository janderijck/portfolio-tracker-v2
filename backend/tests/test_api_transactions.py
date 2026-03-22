"""Tests for the /api/transactions CRUD endpoints."""

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_STOCK = {
    "ticker": "AAPL",
    "isin": "US0378331005",
    "name": "Apple Inc.",
    "asset_type": "STOCK",
    "country": "Verenigde Staten",
    "yahoo_ticker": "AAPL",
    "manual_price_tracking": False,
    "pays_dividend": True,
}

SAMPLE_TRANSACTION = {
    "date": "2025-01-15",
    "broker": "DEGIRO",
    "transaction_type": "BUY",
    "name": "Apple Inc.",
    "ticker": "AAPL",
    "isin": "US0378331005",
    "quantity": 10,
    "price_per_share": 150.0,
    "currency": "USD",
    "fees": 2.50,
    "taxes": 0.0,
    "exchange_rate": 0.92,
    "fees_currency": "EUR",
    "notes": "First purchase",
}


def _setup_stock(client):
    """Create the stock that transactions reference."""
    client.post("/api/stocks", json=SAMPLE_STOCK)


def _create_transaction(client, tx=None):
    """POST a transaction and return the response."""
    payload = tx or SAMPLE_TRANSACTION
    return client.post("/api/transactions", json=payload)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListTransactions:
    def test_empty_initially(self, client):
        resp = client.get("/api/transactions")
        assert resp.status_code == 200
        assert resp.json() == []


class TestCreateTransaction:
    def test_create_buy_transaction(self, client):
        _setup_stock(client)
        resp = _create_transaction(client)
        assert resp.status_code == 200

        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert data["transaction_type"] == "BUY"
        assert data["quantity"] == 10
        assert data["price_per_share"] == 150.0
        assert data["fees"] == 2.50
        assert "id" in data

    def test_create_sell_transaction(self, client):
        _setup_stock(client)
        _create_transaction(client)

        sell_tx = {
            **SAMPLE_TRANSACTION,
            "date": "2025-02-01",
            "transaction_type": "SELL",
            "quantity": 5,
            "price_per_share": 160.0,
            "notes": "Partial sell",
        }
        resp = _create_transaction(client, sell_tx)
        assert resp.status_code == 200
        assert resp.json()["transaction_type"] == "SELL"
        assert resp.json()["quantity"] == 5

    def test_created_transaction_appears_in_list(self, client):
        _setup_stock(client)
        _create_transaction(client)

        resp = client.get("/api/transactions")
        assert resp.status_code == 200
        transactions = resp.json()
        assert len(transactions) == 1
        assert transactions[0]["ticker"] == "AAPL"

    def test_filter_transactions_by_ticker(self, client):
        _setup_stock(client)
        _create_transaction(client)

        # Create a second stock + transaction
        client.post("/api/stocks", json={
            **SAMPLE_STOCK,
            "ticker": "MSFT",
            "isin": "US5949181045",
            "name": "Microsoft Corp.",
            "yahoo_ticker": "MSFT",
        })
        client.post("/api/transactions", json={
            **SAMPLE_TRANSACTION,
            "ticker": "MSFT",
            "isin": "US5949181045",
            "name": "Microsoft Corp.",
        })

        # Filter by ticker
        resp = client.get("/api/transactions", params={"ticker": "AAPL"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["ticker"] == "AAPL"


class TestUpdateTransaction:
    def test_update_transaction(self, client):
        _setup_stock(client)
        create_resp = _create_transaction(client)
        tx_id = create_resp.json()["id"]

        updated_tx = {
            **SAMPLE_TRANSACTION,
            "quantity": 20,
            "price_per_share": 155.0,
            "notes": "Updated quantity",
        }
        resp = client.put(f"/api/transactions/{tx_id}", json=updated_tx)
        assert resp.status_code == 200
        data = resp.json()
        assert data["quantity"] == 20
        assert data["price_per_share"] == 155.0
        assert data["notes"] == "Updated quantity"

    def test_update_nonexistent_transaction(self, client):
        resp = client.put("/api/transactions/99999", json=SAMPLE_TRANSACTION)
        assert resp.status_code == 404


class TestDeleteTransaction:
    def test_delete_transaction(self, client):
        _setup_stock(client)
        create_resp = _create_transaction(client)
        tx_id = create_resp.json()["id"]

        resp = client.delete(f"/api/transactions/{tx_id}")
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"].lower()

        # Verify it's gone
        all_tx = client.get("/api/transactions").json()
        assert len(all_tx) == 0

    def test_delete_nonexistent_transaction(self, client):
        resp = client.delete("/api/transactions/99999")
        assert resp.status_code == 404
