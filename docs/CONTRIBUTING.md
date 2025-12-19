# Contributing Guide

Bedankt voor je interesse in het bijdragen aan Portfolio Tracker! Deze gids helpt je op weg.

## Inhoudsopgave

- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Branch Strategie](#branch-strategie)
- [Pull Request Process](#pull-request-process)
- [Testing](#testing)
- [Architecture Guidelines](#architecture-guidelines)

---

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (optioneel)
- Git

### Backend Setup

```bash
cd backend

# Maak virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Installeer dependencies
pip install -r requirements.txt

# Start development server
uvicorn app.main:app --reload --port 8001
```

### Frontend Setup

```bash
cd frontend

# Installeer dependencies
npm install

# Start development server
npm run dev
```

### Docker Setup (Alternatief)

```bash
docker-compose up --build
```

---

## Code Style

### Python (Backend)

We volgen PEP 8 met enkele aanpassingen:

```python
# Functies: snake_case
def calculate_holding_metrics(transactions: list, current_price: float) -> dict:
    pass

# Classes: PascalCase
class PortfolioHolding(BaseModel):
    pass

# Constants: UPPER_SNAKE_CASE
DEFAULT_EXCHANGE_RATE = 1.0

# Private functions: _leading_underscore
def _get_finnhub_client():
    pass
```

**Docstrings:**

```python
def calculate_holding_metrics(transactions: list, current_price: float, exchange_rate: float) -> dict:
    """
    Berekent metrics voor een holding op basis van transacties.
    
    Args:
        transactions: Lijst van transactie dictionaries
        current_price: Huidige prijs van het aandeel
        exchange_rate: Wisselkoers naar EUR
        
    Returns:
        Dictionary met quantity, avg_purchase_price, total_invested, etc.
    """
    pass
```

**Imports:**

```python
# Standard library
from datetime import date
from typing import Optional, List

# Third party
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Local
from .models import Transaction
from .services.database import get_db
```

### TypeScript (Frontend)

```typescript
// Functions: camelCase
function calculateGainLoss(invested: number, currentValue: number): number {
  return currentValue - invested;
}

// Components: PascalCase
function PortfolioTable({ holdings }: PortfolioTableProps) {
  return <table>...</table>;
}

// Types/Interfaces: PascalCase
interface PortfolioHolding {
  ticker: string;
  quantity: number;
  currentPrice: number | null;
}

// Constants: UPPER_SNAKE_CASE
const DEFAULT_DATE_FORMAT = 'DD/MM/YYYY';

// Files: camelCase.ts of PascalCase.tsx
// - Components: Dashboard.tsx, StockDetail.tsx
// - Utilities: formatting.ts, calculations.ts
```

**Component Structure:**

```typescript
// 1. Imports
import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';

// 2. Types
interface Props {
  ticker: string;
}

// 3. Component
export function StockCard({ ticker }: Props) {
  // 3a. Hooks
  const [isOpen, setIsOpen] = useState(false);
  const { data, isLoading } = useQuery({...});

  // 3b. Handlers
  const handleClick = () => {
    setIsOpen(!isOpen);
  };

  // 3c. Render
  if (isLoading) return <Skeleton />;
  
  return (
    <div onClick={handleClick}>
      {data.name}
    </div>
  );
}
```

---

## Branch Strategie

### Branch Namen

```
feature/add-dividend-calendar
bugfix/fix-currency-conversion
refactor/extract-calculation-utils
docs/update-api-documentation
```

### Workflow

```
main
  │
  ├── feature/add-watchlist
  │     ├── commit: Add watchlist page component
  │     ├── commit: Add API endpoint for watchlist
  │     └── commit: Add tests for watchlist
  │
  └── merge via Pull Request
```

### Commit Messages

Gebruik duidelijke, beschrijvende commit messages:

```
# Goed
Add dividend history fetch endpoint
Fix currency conversion for USD accounts
Refactor portfolio calculations to separate module
Update API documentation with new endpoints

# Slecht
fix bug
update
wip
asdfasdf
```

---

## Pull Request Process

### Voordat je een PR opent

1. **Zorg dat je code compileert zonder errors**
   ```bash
   # Frontend
   cd frontend && npm run build
   
   # Backend (type checking optioneel)
   cd backend && python -m py_compile app/main.py
   ```

2. **Test je wijzigingen lokaal**

3. **Update documentatie indien nodig**

### PR Checklist

- [ ] Code volgt de style guidelines
- [ ] Geen console.log/print statements in productie code
- [ ] Nieuwe functies hebben docstrings/comments
- [ ] Eventuele nieuwe API endpoints zijn gedocumenteerd
- [ ] TypeScript types matchen backend Pydantic models
- [ ] Geen hardcoded credentials of API keys

### PR Template

```markdown
## Beschrijving
Korte beschrijving van de wijzigingen.

## Type Wijziging
- [ ] Feature (nieuwe functionaliteit)
- [ ] Bugfix
- [ ] Refactor
- [ ] Documentation
- [ ] Other

## Geteste Scenario's
- [ ] Scenario 1: ...
- [ ] Scenario 2: ...

## Screenshots (indien UI wijzigingen)
```

---

## Testing

### Backend Tests

```bash
cd backend

# Run tests (wanneer beschikbaar)
pytest

# Run specific test
pytest tests/test_calculations.py

# With coverage
pytest --cov=app
```

### Frontend Tests

```bash
cd frontend

# Run tests (wanneer beschikbaar)
npm test

# With coverage
npm test -- --coverage
```

### Wat te testen

**Backend:**
- Pure calculation functions (highest priority)
- API endpoint responses
- Database operations

**Frontend:**
- Utility/formatting functions
- Component rendering
- User interactions

---

## Architecture Guidelines

Zie [CLAUDE.md](../CLAUDE.md) voor gedetailleerde architectuur richtlijnen.

### Kernprincipes

1. **Separation of Concerns**
   - API routes: alleen routing en validation
   - Services: business logic
   - Database: alleen data access
   - Utils: pure calculation functions

2. **Single Responsibility**
   - Elke functie doet ONE ding
   - Geen "god functions"

3. **Composability**
   - Kleine, herbruikbare functies
   - Onafhankelijk testbaar

### Code Locatie

| Type Code | Backend | Frontend |
|-----------|---------|----------|
| API/Routes | `app/main.py` | - |
| Data Models | `app/models.py` | `types/index.ts` |
| Business Logic | `app/services/` | `hooks/` |
| Pure Calculations | `app/services/calculations.py` | `utils/` |
| Database Access | `app/services/database.py` | - |
| API Calls | - | `api/client.ts` |
| Components | - | `components/`, `pages/` |

### Veelgemaakte Fouten

```python
# FOUT: Fees in average price
avg_price = (total_cost + fees) / quantity

# GOED: Fees apart houden
avg_price = total_cost / quantity
total_fees = sum(tx['fees'] for tx in transactions)
```

```typescript
// FOUT: Inline calculations in JSX
<td>{(holding.currentValue - holding.totalInvested).toFixed(2)}</td>

// GOED: Gebruik utility function
<td>{formatCurrency(calculateGainLoss(holding))}</td>
```

```python
# FOUT: Business logic in route
@app.get("/api/portfolio")
async def get_portfolio():
    # 100 lines of calculation code...
    
# GOED: Delegate to service
@app.get("/api/portfolio")
async def get_portfolio():
    return portfolio_service.get_portfolio_with_metrics()
```

---

## Vragen?

Open een issue met je vraag, of bekijk bestaande issues voor antwoorden.

## Licentie

Door bij te dragen aan dit project, ga je akkoord dat je bijdragen worden gelicenseerd onder de MIT licentie.
