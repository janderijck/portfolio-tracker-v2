# Changelog

Alle belangrijke wijzigingen aan dit project worden gedocumenteerd in dit bestand.

Het formaat is gebaseerd op [Keep a Changelog](https://keepachangelog.com/nl/1.0.0/),
en dit project volgt [Semantic Versioning](https://semver.org/lang/nl/).

## [Unreleased]

### Added
- Azure Container Apps deployment configuratie
- GitHub Actions CI/CD pipeline
- Uitgebreide documentatie (DEPLOYMENT.md, API.md, CONTRIBUTING.md)

---

## [2.0.0] - 2024-01-15

### Added
- Volledige herschrijving van de applicatie
- FastAPI backend met Pydantic v2
- React 18 frontend met TypeScript
- TanStack Query voor data fetching
- Tailwind CSS voor styling
- Dark mode ondersteuning
- Portfolio overzicht met real-time koersen
- Transactie management (koop/verkoop)
- Dividend tracking met belasting berekeningen
  - US bronbelasting (15%)
  - Belgische roerende voorheffing
- Automatische dividend import van Yahoo Finance
- Multi-broker ondersteuning (DEGIRO, IBKR)
- EUR/USD valuta ondersteuning
- Wisselkoers tracking per transactie
- Handmatige prijs tracking voor private equity
- Watchlist voor stocks zonder positie
- Interactieve grafieken met Recharts
- Kosten analyse per broker
- Portfolio allocatie analyse
  - Per broker
  - Per land
  - Per asset type
- Historische koersgrafieken
- Stock detail pagina met transactie geschiedenis
- Settings pagina
  - Datum formaat instelling
  - Finnhub API key configuratie
- Docker Compose setup voor development

### Technical
- SQLite database
- yfinance integratie voor marktdata
- Finnhub integratie (optioneel)
- CORS configuratie
- Type-safe API met Pydantic models
- React Query caching

---

## [1.0.0] - 2023-06-01

### Added
- Eerste versie van Portfolio Tracker
- Basis portfolio tracking
- Simpele transactie registratie

---

## Versie Nummering

- **MAJOR** versie: incompatibele API wijzigingen
- **MINOR** versie: nieuwe functionaliteit, backwards compatible
- **PATCH** versie: bug fixes, backwards compatible

## Links

- [GitHub Repository](https://github.com/yourusername/portfolio-tracker-v2)
- [Issue Tracker](https://github.com/yourusername/portfolio-tracker-v2/issues)
