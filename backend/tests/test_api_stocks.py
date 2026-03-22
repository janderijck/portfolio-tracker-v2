"""Tests for the /api/stocks CRUD endpoints."""

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


def _create_stock(client, stock=None):
    """Helper to POST a stock and return the response."""
    payload = stock or SAMPLE_STOCK
    return client.post("/api/stocks", json=payload)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateStock:
    def test_create_stock_returns_201_or_200(self, client):
        resp = _create_stock(client)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert data["name"] == "Apple Inc."
        assert "id" in data

    def test_create_duplicate_stock_returns_400(self, client):
        _create_stock(client)
        resp = _create_stock(client)
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]


class TestListStocks:
    def test_list_stocks_empty(self, client):
        resp = client.get("/api/stocks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_stocks_after_create(self, client):
        _create_stock(client)
        resp = client.get("/api/stocks")
        assert resp.status_code == 200
        stocks = resp.json()
        assert len(stocks) == 1
        assert stocks[0]["ticker"] == "AAPL"


class TestGetStockDetail:
    def test_get_stock_detail(self, client):
        _create_stock(client)
        resp = client.get("/api/stocks/AAPL")
        assert resp.status_code == 200
        data = resp.json()
        # The detail endpoint returns {"info": ..., "transactions": ..., ...}
        assert data["info"]["ticker"] == "AAPL"
        assert isinstance(data["transactions"], list)
        assert isinstance(data["dividends"], list)

    def test_get_stock_detail_not_found(self, client):
        resp = client.get("/api/stocks/NONEXISTENT")
        assert resp.status_code == 200
        data = resp.json()
        # When stock not found, info is None
        assert data["info"] is None


class TestUpdateStock:
    def test_update_stock(self, client):
        _create_stock(client)

        updated = {**SAMPLE_STOCK, "name": "Apple Inc. (Updated)"}
        resp = client.put("/api/stocks/AAPL", json=updated)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Apple Inc. (Updated)"

    def test_update_nonexistent_stock(self, client):
        resp = client.put("/api/stocks/NONEXISTENT", json=SAMPLE_STOCK)
        assert resp.status_code == 404


class TestDeleteStock:
    def test_delete_stock(self, client):
        _create_stock(client)
        resp = client.delete("/api/stocks/AAPL")
        assert resp.status_code == 200

        # Verify it's gone from the list
        stocks = client.get("/api/stocks").json()
        assert len(stocks) == 0

    def test_delete_nonexistent_stock(self, client):
        resp = client.delete("/api/stocks/NONEXISTENT")
        assert resp.status_code == 404
