# Portfolio Tracker - Architecture Guidelines

## Project Overview
A portfolio tracking application for Belgian investors to manage stocks, dividends, and transactions across multiple brokers (DEGIRO, IBKR).

## Architecture Principles

### 1. Separation of Concerns
- **Backend**: FastAPI for API, separate service layers for business logic
- **Frontend**: React with hooks for state, separate utility functions for calculations
- **Database**: SQLite with clear schema, no calculated fields stored

### 2. Single Responsibility Principle
Each module/function should have ONE clear purpose:
- API endpoints: Route handling and validation only
- Services: Business logic and data orchestration
- Repositories/Database: Data access only
- Utils: Pure calculation functions

### 3. Composability
- Small, reusable functions that can be combined
- No god functions that do everything
- Each calculation step should be testable independently

### 4. Data Flow
```
Frontend -> API -> Service -> Database
                      |
                   Utils (calculations)
```

## Code Structure

### Backend (`/backend/app/`)
```
app/
├── main.py              # FastAPI app, routes only
├── models.py            # Pydantic models for validation
├── services/
│   ├── database.py      # Database access functions
│   ├── portfolio.py     # Portfolio business logic
│   ├── market_data.py   # Yahoo Finance integration
│   └── calculations.py  # Pure calculation functions
```

### Frontend (`/frontend/src/`)
```
src/
├── api/client.ts        # API calls only
├── hooks/               # React Query hooks
├── pages/               # Page components
├── components/          # Reusable UI components
├── utils/
│   └── calculations.ts  # Pure calculation functions
└── types/index.ts       # TypeScript types
```

## Calculation Rules

### Portfolio Value Calculations
All calculations happen at display time, not storage time.

1. **Average Purchase Price** = Total Cost / Quantity
   - Total Cost = Σ(quantity × price_per_share) for all BUY transactions
   - Do NOT include fees in average price

2. **Current Value** = Quantity × Current Price

3. **Gain/Loss** = Current Value - Total Invested
   - Total Invested = Σ(quantity × price_per_share) for all BUY transactions

4. **Gain/Loss %** = (Gain/Loss / Total Invested) × 100

### Currency Handling
- Store transactions in original currency
- Convert to EUR only at display time using current exchange rate
- Exchange rate stored per transaction for historical accuracy

### Fee Handling
- Fees are tracked separately, NOT included in purchase price
- Display as separate column/field

## Database Schema Principles

### What to Store
- Raw transaction data (date, quantity, price, fees, currency)
- User-entered values only
- No calculated fields

### What NOT to Store
- Average prices (calculate from transactions)
- Current values (fetch from market data)
- Gain/loss (calculate at runtime)

## Naming Conventions

### Backend (Python)
- Functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Files: `snake_case.py`

### Frontend (TypeScript)
- Functions: `camelCase`
- Components: `PascalCase`
- Types/Interfaces: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Files: `camelCase.ts` or `PascalCase.tsx`

## API Design

### Endpoints
- `GET /api/portfolio` - Get holdings with current values
- `GET /api/transactions` - Get raw transaction data
- `POST /api/transactions` - Create transaction
- `PUT /api/transactions/{id}` - Update transaction
- `DELETE /api/transactions/{id}` - Delete transaction
- Same pattern for dividends

### Response Format
- Return raw data from database
- Let frontend handle display formatting
- Include all fields needed for calculations

## Testing Strategy
- Unit tests for calculation functions
- Integration tests for API endpoints
- All calculation functions should be pure (no side effects)

## Performance Considerations
- Cache market data (prices, exchange rates) with TTL
- Lazy load detail views
- Paginate large lists

## Dutch Terminology
- Aandeel = Stock
- Dividend = Dividend
- Transactie = Transaction
- Koop = Buy
- Verkoop = Sell
- Kosten = Fees
- Belasting = Tax
- Wisselkoers = Exchange rate
- Geïnvesteerd = Invested
- Winst/Verlies (W/V) = Gain/Loss

## Common Mistakes to Avoid
1. ❌ Including fees in average purchase price
2. ❌ Storing calculated values in database
3. ❌ Mixing business logic in API routes
4. ❌ Inline calculations in JSX
5. ❌ God functions that do multiple things
6. ✅ Pure functions for calculations
7. ✅ Clear separation of data access and business logic
8. ✅ TypeScript types matching backend models exactly
