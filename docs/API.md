# API Documentation

Portfolio Tracker API v2.0.0

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: `https://ca-portfolio-backend.<id>.westeurope.azurecontainerapps.io`

## Interactive Documentation

FastAPI biedt automatische interactieve documentatie:
- **Swagger UI**: `{base_url}/docs`
- **ReDoc**: `{base_url}/redoc`

---

## Endpoints Overzicht

| Categorie | Endpoints |
|-----------|-----------|
| [Portfolio](#portfolio) | 1 |
| [Transactions](#transactions) | 4 |
| [Dividends](#dividends) | 5 |
| [Stocks](#stocks) | 8 |
| [Brokers](#brokers) | 2 |
| [Analysis](#analysis) | 4 |
| [Settings](#settings) | 3 |
| [Manual Prices](#manual-prices) | 4 |

---

## Portfolio

### GET /api/portfolio

Haalt alle portfolio holdings op met berekende metrics.

**Response** `200 OK`

```json
{
  "holdings": [
    {
      "ticker": "AAPL",
      "isin": "US0378331005",
      "name": "Apple Inc.",
      "broker": "DEGIRO",
      "quantity": 10,
      "avg_purchase_price": 150.00,
      "total_invested": 1500.00,
      "total_invested_eur": 1380.00,
      "total_fees": 2.50,
      "currency": "USD",
      "current_price": 175.00,
      "current_value": 1750.00,
      "gain_loss": 250.00,
      "gain_loss_percent": 16.67,
      "is_usd_account": true,
      "manual_price_date": null,
      "pays_dividend": true
    }
  ],
  "summary": {
    "total_invested_eur": 1380.00,
    "total_current_value_eur": 1610.00,
    "total_gain_loss_eur": 230.00,
    "total_gain_loss_percent": 16.67
  }
}
```

---

## Transactions

### GET /api/transactions

Haalt alle transacties op.

**Query Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ticker` | string | No | Filter op ticker symbol |

**Response** `200 OK`

```json
[
  {
    "id": 1,
    "date": "2024-01-15",
    "broker": "DEGIRO",
    "transaction_type": "BUY",
    "name": "Apple Inc.",
    "ticker": "AAPL",
    "isin": "US0378331005",
    "quantity": 10,
    "price_per_share": 150.00,
    "currency": "USD",
    "fees": 2.50,
    "taxes": 0.00,
    "exchange_rate": 0.92,
    "fees_currency": "EUR",
    "notes": null
  }
]
```

### POST /api/transactions

Maakt een nieuwe transactie aan.

**Request Body**

```json
{
  "date": "2024-01-15",
  "broker": "DEGIRO",
  "transaction_type": "BUY",
  "name": "Apple Inc.",
  "ticker": "AAPL",
  "isin": "US0378331005",
  "quantity": 10,
  "price_per_share": 150.00,
  "currency": "USD",
  "fees": 2.50,
  "taxes": 0.00,
  "exchange_rate": 0.92,
  "fees_currency": "EUR",
  "notes": "Eerste aankoop"
}
```

**Response** `200 OK`

```json
{
  "id": 1,
  "date": "2024-01-15",
  "broker": "DEGIRO",
  "transaction_type": "BUY",
  ...
}
```

### PUT /api/transactions/{transaction_id}

Update een bestaande transactie.

**Path Parameters**
| Parameter | Type | Description |
|-----------|------|-------------|
| `transaction_id` | integer | Transaction ID |

**Request Body**: Zelfde als POST

**Response** `200 OK` of `404 Not Found`

### DELETE /api/transactions/{transaction_id}

Verwijdert een transactie.

**Response** `200 OK`

```json
{
  "message": "Transaction deleted"
}
```

---

## Dividends

### GET /api/dividends

Haalt alle dividenden op.

**Query Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ticker` | string | No | Filter op ticker symbol |

**Response** `200 OK`

```json
[
  {
    "id": 1,
    "ticker": "AAPL",
    "isin": "US0378331005",
    "ex_date": "2024-02-09",
    "bruto_amount": 9.60,
    "currency": "USD",
    "withheld_tax": 1.44,
    "net_amount": 8.16,
    "received": true,
    "notes": "Q1 2024 dividend"
  }
]
```

### POST /api/dividends

Maakt een nieuw dividend record aan.

**Request Body**

```json
{
  "ticker": "AAPL",
  "isin": "US0378331005",
  "ex_date": "2024-02-09",
  "bruto_amount": 9.60,
  "currency": "USD",
  "withheld_tax": 1.44,
  "net_amount": 8.16,
  "received": true,
  "notes": null
}
```

### PUT /api/dividends/{dividend_id}

Update een dividend record.

### DELETE /api/dividends/{dividend_id}

Verwijdert een dividend record.

### POST /api/dividends/fetch-history/{ticker}

Haalt dividend geschiedenis op van Yahoo Finance en voegt toe aan database.

**Features:**
- Haalt alleen dividenden op vanaf eerste aankoopdatum
- Berekent automatisch totaal dividend op basis van aantal aandelen
- Past bronbelasting toe gebaseerd op land

**Response** `200 OK`

```json
{
  "message": "Added 4 dividends",
  "count": 4,
  "total_found": 6
}
```

---

## Stocks

### GET /api/stocks

Haalt alle opgeslagen stocks op.

### GET /api/stocks/search

Zoekt stocks in lokale database en Yahoo Finance.

**Query Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | Yes | Zoekterm (ticker, naam, of ISIN) |

**Response** `200 OK`

```json
[
  {
    "ticker": "AAPL",
    "isin": "US0378331005",
    "name": "Apple Inc.",
    "asset_type": "STOCK",
    "country": "Verenigde Staten",
    "current_price": 175.00,
    "currency": "USD",
    "pays_dividend": true,
    "dividend_yield": 0.5,
    "from_yahoo": true
  }
]
```

### GET /api/stocks/lookup/{isin}

Zoekt stock informatie op via ISIN.

### GET /api/stocks/{ticker}

Haalt gedetailleerde informatie op over een stock.

**Response** `200 OK`

```json
{
  "info": {
    "id": 1,
    "ticker": "AAPL",
    "isin": "US0378331005",
    "name": "Apple Inc.",
    "asset_type": "STOCK",
    "country": "Verenigde Staten",
    "manual_price_tracking": false,
    "pays_dividend": true
  },
  "transactions": [...],
  "dividends": [...],
  "current_price": {
    "current_price": 175.00,
    "currency": "USD"
  }
}
```

### GET /api/stocks/{ticker}/history

Haalt historische koersdata op.

**Query Parameters**
| Parameter | Type | Default | Options |
|-----------|------|---------|---------|
| `period` | string | `1y` | `1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `ytd`, `max` |

**Response** `200 OK`

```json
[
  {"date": "2024-01-02", "price": 185.64},
  {"date": "2024-01-03", "price": 184.25},
  ...
]
```

### POST /api/stocks

Voegt een nieuwe stock toe.

### PUT /api/stocks/{ticker}

Update stock informatie.

### DELETE /api/stocks/{ticker}

Verwijdert een stock.

### GET /api/watchlist

Haalt stocks zonder posities op (watchlist).

---

## Brokers

### GET /api/brokers

Haalt lijst van beschikbare brokers op.

**Response** `200 OK`

```json
["DEGIRO", "IBKR", "Bolero"]
```

### POST /api/brokers

Voegt een nieuwe broker toe.

**Request Body**

```json
{
  "broker_name": "Saxo Bank"
}
```

---

## Analysis

### GET /api/analysis/performance

Haalt portfolio performance samenvatting op.

**Response** `200 OK`

```json
{
  "total_invested": 10000.00,
  "current_value": 12500.00,
  "total_gain_loss": 2500.00,
  "total_gain_loss_percent": 25.00,
  "total_dividends": 350.00,
  "total_return": 2850.00,
  "total_return_percent": 28.50,
  "best_performer": "NVDA",
  "best_performer_percent": 85.50,
  "worst_performer": "INTC",
  "worst_performer_percent": -15.30
}
```

### GET /api/analysis/dividends

Haalt dividend analyse samenvatting op.

**Response** `200 OK`

```json
{
  "total_received": 500.00,
  "total_withheld_tax": 75.00,
  "total_net": 425.00,
  "dividend_yield": 4.25,
  "by_ticker": {
    "AAPL": {"total": 96.00, "count": 4},
    "MSFT": {"total": 120.00, "count": 4}
  },
  "by_year": {
    "2023": 200.00,
    "2024": 225.00
  }
}
```

### GET /api/analysis/costs

Haalt kosten analyse op.

**Response** `200 OK`

```json
{
  "total_fees": 125.50,
  "total_taxes": 0.00,
  "transaction_count": 25,
  "avg_fee_per_transaction": 5.02,
  "by_broker": {
    "DEGIRO": {"total": 75.50, "count": 15},
    "IBKR": {"total": 50.00, "count": 10}
  },
  "fees_as_percent_of_invested": 1.25
}
```

### GET /api/analysis/allocation

Haalt portfolio allocatie analyse op.

**Response** `200 OK`

```json
{
  "by_broker": [
    {"name": "DEGIRO", "value": 8000.00, "percentage": 64.00},
    {"name": "IBKR", "value": 4500.00, "percentage": 36.00}
  ],
  "by_country": [
    {"name": "Verenigde Staten", "value": 10000.00, "percentage": 80.00},
    {"name": "Nederland", "value": 2500.00, "percentage": 20.00}
  ],
  "by_asset_type": [
    {"name": "STOCK", "value": 11000.00, "percentage": 88.00},
    {"name": "REIT", "value": 1500.00, "percentage": 12.00}
  ]
}
```

---

## Settings

### GET /api/settings

Haalt gebruikersinstellingen op.

**Response** `200 OK`

```json
{
  "date_format": "DD/MM/YYYY",
  "finnhub_api_key": null
}
```

### PUT /api/settings

Update gebruikersinstellingen.

**Request Body**

```json
{
  "date_format": "DD/MM/YYYY",
  "finnhub_api_key": "your-api-key"
}
```

### POST /api/settings/test-finnhub

Test de Finnhub API verbinding.

**Response** `200 OK`

```json
{
  "success": true,
  "message": "Finnhub API werkt correct!",
  "test_data": {
    "ticker": "AAPL",
    "price": 175.00,
    "change_percent": 1.25
  }
}
```

---

## Manual Prices

Voor stocks zonder Yahoo Finance data (private equity, etc.).

### GET /api/stocks/{ticker}/prices

Haalt alle handmatige prijzen op voor een stock.

**Response** `200 OK`

```json
[
  {
    "id": 1,
    "ticker": "PRIVATE1",
    "date": "2024-01-31",
    "price": 125.00,
    "currency": "EUR",
    "notes": "Maandelijkse NAV update"
  }
]
```

### POST /api/stocks/{ticker}/prices

Voegt een handmatige prijs toe.

**Request Body**

```json
{
  "ticker": "PRIVATE1",
  "date": "2024-01-31",
  "price": 125.00,
  "currency": "EUR",
  "notes": null
}
```

### PUT /api/stocks/{ticker}/prices/{price_id}

Update een handmatige prijs.

### DELETE /api/stocks/{ticker}/prices/{price_id}

Verwijdert een handmatige prijs.

---

## Error Responses

### 400 Bad Request

```json
{
  "detail": "Invalid request body"
}
```

### 404 Not Found

```json
{
  "detail": "Transaction not found"
}
```

### 422 Validation Error

```json
{
  "detail": [
    {
      "loc": ["body", "quantity"],
      "msg": "value is not a valid integer",
      "type": "type_error.integer"
    }
  ]
}
```

### 500 Internal Server Error

```json
{
  "detail": "Error fetching historical data: ..."
}
```

---

## Data Types

### TransactionType (Enum)

| Value | Description |
|-------|-------------|
| `BUY` | Aankoop |
| `SELL` | Verkoop |

### AssetType (Enum)

| Value | Description |
|-------|-------------|
| `STOCK` | Aandeel |
| `REIT` | Real Estate Investment Trust |

### Currency

Veelgebruikte valuta codes:
- `EUR` - Euro
- `USD` - US Dollar
- `GBP` - Britse Pond

---

## Rate Limiting

De API heeft momenteel geen rate limiting. Bij integratie met Yahoo Finance gelden hun fair use policies.

## Authentication

De API heeft momenteel geen authenticatie. Dit is bedoeld voor persoonlijk gebruik.

Voor productie gebruik wordt aangeraden om authenticatie toe te voegen via:
- Azure AD / Entra ID
- API Keys
- OAuth 2.0
