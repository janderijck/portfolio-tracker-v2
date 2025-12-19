# Portfolio Tracker v2

Modern portfolio tracking application for Belgian investors. Track stocks, dividends, and transactions across multiple brokers (DEGIRO, IBKR).

## Features

- Portfolio overview with EUR/USD currency support
- Transaction management (buy/sell)
- Dividend tracking with tax calculations (US withholding, Belgian RV)
- Automatic dividend import from Yahoo Finance
- Cash flow analysis
- FX gain/loss analysis
- Cost tracking per broker
- Watchlist for stocks without positions
- Dark mode support
- Interactive charts (Recharts)
- Manual price tracking for private equity

## Tech Stack

**Backend:**
- FastAPI
- SQLite
- Pydantic v2
- yfinance for market data

**Frontend:**
- React 18 + TypeScript
- Vite
- Tailwind CSS
- TanStack Query
- Recharts
- Lucide icons

## Quick Start

### Development

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Docker

```bash
docker-compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Documentation

| Document | Description |
|----------|-------------|
| [API Documentation](docs/API.md) | Complete API reference with all endpoints |
| [Deployment Guide](docs/DEPLOYMENT.md) | Azure Container Apps deployment instructions |
| [Contributing Guide](docs/CONTRIBUTING.md) | How to contribute to this project |
| [Changelog](CHANGELOG.md) | Version history and changes |
| [Architecture](CLAUDE.md) | Architecture guidelines and principles |

## Azure Deployment

This application is designed to run on Azure Container Apps. See the [Deployment Guide](docs/DEPLOYMENT.md) for detailed instructions.

### Quick Deploy

```bash
cd infra
./deploy.sh
```

### CI/CD

The repository includes GitHub Actions workflow for automatic deployment on push to `main`. See [.github/workflows/deploy.yml](.github/workflows/deploy.yml).

Required GitHub Secrets:
- `AZURE_CREDENTIALS` - Azure Service Principal credentials
- `AZURE_SUBSCRIPTION_ID` - Your Azure subscription ID
- `ACR_PASSWORD` - Azure Container Registry password

## API Endpoints

| Category | Endpoints |
|----------|-----------|
| Portfolio | `GET /api/portfolio` |
| Transactions | `GET/POST/PUT/DELETE /api/transactions` |
| Dividends | `GET/POST/PUT/DELETE /api/dividends` |
| Stocks | `GET/POST/PUT/DELETE /api/stocks` |
| Analysis | `GET /api/analysis/performance`, `costs`, `dividends`, `allocation` |
| Settings | `GET/PUT /api/settings` |

See [API Documentation](docs/API.md) for complete reference.

## Database

SQLite database stored in `data/portfolio.db`. Tables:
- `transactions` - Buy/sell transactions
- `dividends` - Dividend records
- `stocks` - Stock information
- `manual_prices` - Manual price entries for private equity
- `user_settings` - User preferences
- `broker_settings` - Broker configuration

## Project Structure

```
portfolio-tracker-v2/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI routes
│   │   ├── models.py            # Pydantic models
│   │   └── services/
│   │       ├── database.py      # Database operations
│   │       ├── market_data.py   # Yahoo Finance integration
│   │       └── calculations.py  # Business logic
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/client.ts        # API client
│   │   ├── hooks/               # React Query hooks
│   │   ├── pages/               # Page components
│   │   ├── components/          # Reusable components
│   │   ├── types/index.ts       # TypeScript types
│   │   └── utils/               # Utility functions
│   ├── Dockerfile
│   └── package.json
├── infra/
│   ├── main.bicep               # Azure Infrastructure as Code
│   └── deploy.sh                # Deployment script
├── docs/
│   ├── API.md
│   ├── DEPLOYMENT.md
│   └── CONTRIBUTING.md
├── .github/workflows/
│   └── deploy.yml               # CI/CD pipeline
├── docker-compose.yml
└── README.md
```

## License

MIT
