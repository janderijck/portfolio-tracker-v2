import sqlite3
from pathlib import Path
from contextlib import contextmanager

DATABASE_PATH = Path(__file__).parent.parent.parent / "data" / "portfolio.db"


def get_connection():
    """Get database connection and ensure tables exist."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    _create_tables(conn)
    return conn


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def _create_tables(conn):
    """Create all required tables if they don't exist."""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        broker TEXT NOT NULL,
        transaction_type TEXT NOT NULL,
        name TEXT NOT NULL,
        ticker TEXT NOT NULL,
        isin TEXT,
        quantity INTEGER NOT NULL,
        price_per_share REAL NOT NULL,
        currency TEXT DEFAULT 'EUR',
        fees REAL DEFAULT 0,
        taxes REAL DEFAULT 0,
        exchange_rate REAL DEFAULT 1.0,
        fees_currency TEXT DEFAULT 'EUR',
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS dividends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        isin TEXT,
        ex_date TEXT NOT NULL,
        bruto_amount REAL NOT NULL,
        currency TEXT DEFAULT 'USD',
        notes TEXT,
        received INTEGER DEFAULT 0,
        tax_paid INTEGER DEFAULT 0,
        withheld_amount REAL,
        additional_tax_due REAL,
        net_received REAL
    );

    CREATE TABLE IF NOT EXISTS cash_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        broker TEXT NOT NULL,
        transaction_type TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'EUR',
        source_amount REAL,
        source_currency TEXT,
        exchange_rate REAL,
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS broker_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        broker_name TEXT NOT NULL UNIQUE,
        country TEXT DEFAULT 'België',
        has_w8ben INTEGER DEFAULT 0,
        w8ben_expiry_date TEXT,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS stock_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL UNIQUE,
        isin TEXT,
        name TEXT,
        asset_type TEXT DEFAULT 'STOCK',
        country TEXT DEFAULT 'Verenigde Staten',
        custom_dividend_tax_rate REAL,
        yahoo_ticker TEXT,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS price_cache (
        ticker TEXT PRIMARY KEY,
        current_price REAL,
        change_percent REAL,
        currency TEXT,
        updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS exchange_rate_cache (
        pair TEXT PRIMARY KEY,
        rate REAL,
        cached_date TEXT
    );
    """)
    conn.commit()


# Transaction operations
def insert_transaction(conn, data: dict) -> int:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (
            date, broker, transaction_type, name, ticker, isin,
            quantity, price_per_share, currency, fees, taxes,
            exchange_rate, fees_currency, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['date'], data['broker'], data['transaction_type'],
        data['name'], data['ticker'], data['isin'],
        data['quantity'], data['price_per_share'], data['currency'],
        data['fees'], data['taxes'], data['exchange_rate'],
        data['fees_currency'], data.get('notes')
    ))
    conn.commit()
    return cursor.lastrowid


def get_all_transactions(conn, ticker: str = None):
    cursor = conn.cursor()
    if ticker:
        cursor.execute(
            "SELECT * FROM transactions WHERE ticker = ? ORDER BY date DESC",
            (ticker,)
        )
    else:
        cursor.execute("SELECT * FROM transactions ORDER BY date DESC")
    return [dict(row) for row in cursor.fetchall()]


def get_transaction_by_id(conn, transaction_id: int):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def delete_transaction(conn, transaction_id: int):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    conn.commit()
    return cursor.rowcount > 0


# Dividend operations
def insert_dividend(conn, data: dict) -> int:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO dividends (
            ticker, isin, ex_date, bruto_amount, currency, notes,
            received, tax_paid, withheld_amount, additional_tax_due, net_received
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['ticker'], data['isin'], data['ex_date'],
        data['bruto_amount'], data['currency'], data.get('notes'),
        1 if data.get('received') else 0,
        1 if data.get('tax_paid') else 0,
        data.get('withheld_amount'),
        data.get('additional_tax_due'),
        data.get('net_received')
    ))
    conn.commit()
    return cursor.lastrowid


def get_all_dividends(conn, ticker: str = None):
    cursor = conn.cursor()
    if ticker:
        cursor.execute(
            "SELECT * FROM dividends WHERE ticker = ? ORDER BY ex_date DESC",
            (ticker,)
        )
    else:
        cursor.execute("SELECT * FROM dividends ORDER BY ex_date DESC")
    return [dict(row) for row in cursor.fetchall()]


def delete_dividend(conn, dividend_id: int):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dividends WHERE id = ?", (dividend_id,))
    conn.commit()
    return cursor.rowcount > 0


# Cash transaction operations
def insert_cash_transaction(conn, data: dict) -> int:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cash_transactions (
            date, broker, transaction_type, amount, currency,
            source_amount, source_currency, exchange_rate, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['date'], data['broker'], data['transaction_type'],
        data['amount'], data['currency'],
        data.get('source_amount'), data.get('source_currency'),
        data.get('exchange_rate'), data.get('notes')
    ))
    conn.commit()
    return cursor.lastrowid


def get_cash_transactions(conn, broker: str = None):
    cursor = conn.cursor()
    if broker:
        cursor.execute(
            "SELECT * FROM cash_transactions WHERE broker = ? ORDER BY date DESC",
            (broker,)
        )
    else:
        cursor.execute("SELECT * FROM cash_transactions ORDER BY date DESC")
    return [dict(row) for row in cursor.fetchall()]


# Portfolio holdings
def get_portfolio_holdings(conn):
    """Get all holdings with aggregated data."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            ticker, isin, name, currency,
            (SELECT broker FROM transactions t2
             WHERE t2.ticker = t.ticker ORDER BY date DESC LIMIT 1) as broker,
            SUM(CASE WHEN transaction_type = 'BUY' THEN quantity ELSE -quantity END) as total_quantity,
            SUM(CASE WHEN transaction_type = 'BUY' THEN quantity * price_per_share ELSE 0 END) as total_invested,
            SUM(CASE WHEN transaction_type = 'BUY' THEN fees + COALESCE(taxes, 0) ELSE 0 END) as total_fees,
            SUM(CASE WHEN transaction_type = 'BUY' THEN
                quantity * price_per_share * COALESCE(exchange_rate, 1.0) ELSE 0 END) as total_invested_eur,
            SUM(CASE WHEN transaction_type = 'BUY' THEN
                CASE WHEN COALESCE(fees_currency, 'EUR') = 'EUR'
                    THEN fees + COALESCE(taxes, 0)
                    ELSE (fees + COALESCE(taxes, 0)) * COALESCE(exchange_rate, 1.0)
                END
            ELSE 0 END) as total_fees_eur,
            AVG(CASE WHEN transaction_type = 'BUY' THEN COALESCE(exchange_rate, 1.0) END) as avg_exchange_rate
        FROM transactions t
        GROUP BY ticker, isin, name, currency
        HAVING total_quantity > 0
    """)
    return [dict(row) for row in cursor.fetchall()]


# Broker operations
def get_broker_settings(conn, broker_name: str = None):
    cursor = conn.cursor()
    if broker_name:
        cursor.execute(
            "SELECT * FROM broker_settings WHERE broker_name = ?",
            (broker_name,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    else:
        cursor.execute("SELECT * FROM broker_settings")
        return [dict(row) for row in cursor.fetchall()]


def get_available_brokers(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT broker_name FROM broker_settings ORDER BY broker_name")
    return [row[0] for row in cursor.fetchall()]


# Stock info operations
def get_stock_info(conn, ticker: str):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stock_info WHERE ticker = ?", (ticker,))
    row = cursor.fetchone()
    return dict(row) if row else None


# Price cache operations
def get_cached_price(conn, ticker: str):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT current_price, change_percent, currency, updated_at FROM price_cache WHERE ticker = ?",
        (ticker,)
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def save_price_to_cache(conn, ticker: str, price: float, change_percent: float, currency: str):
    from datetime import datetime
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO price_cache (ticker, current_price, change_percent, currency, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """, (ticker, price, change_percent, currency, datetime.now().isoformat()))
    conn.commit()


# Exchange rate cache
def get_cached_exchange_rate(conn, from_currency: str, to_currency: str):
    from datetime import date
    cursor = conn.cursor()
    pair = f"{from_currency}{to_currency}"
    cursor.execute(
        "SELECT rate, cached_date FROM exchange_rate_cache WHERE pair = ?",
        (pair,)
    )
    row = cursor.fetchone()
    if row and row['cached_date'] == date.today().isoformat():
        return row['rate']
    return None


def save_exchange_rate_to_cache(conn, from_currency: str, to_currency: str, rate: float):
    from datetime import date
    cursor = conn.cursor()
    pair = f"{from_currency}{to_currency}"
    cursor.execute("""
        INSERT OR REPLACE INTO exchange_rate_cache (pair, rate, cached_date)
        VALUES (?, ?, ?)
    """, (pair, rate, date.today().isoformat()))
    conn.commit()
