# Portfolio Tracker v2

Modern portfolio tracking application with FastAPI backend and React frontend.

## Features

- Portfolio overview with EUR/USD currency support
- Transaction management (buy/sell)
- Dividend tracking with tax calculations (US withholding, Belgian RV)
- Cash flow analysis
- FX gain/loss analysis
- Cost tracking per broker
- Dark mode support
- Interactive charts (Recharts)

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
uvicorn app.main:app --reload
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

## API Endpoints

- `GET /api/portfolio` - Portfolio holdings with summary
- `GET /api/transactions` - All transactions
- `POST /api/transactions` - Create transaction
- `GET /api/dividends` - All dividends
- `POST /api/dividends` - Create dividend
- `GET /api/stocks/{ticker}` - Stock details
- `GET /api/cash-flow` - Cash flow analysis
- `GET /api/fx-analysis` - FX gain/loss
- `GET /api/costs` - Fee analysis

## Database

SQLite database stored in `data/portfolio.db`. Tables:
- `transactions` - Buy/sell transactions
- `dividends` - Dividend records
- `cash` - Cash deposits/withdrawals

## License

MIT
