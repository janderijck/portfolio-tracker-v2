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
        quantity REAL NOT NULL,
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
        withheld_tax REAL DEFAULT 0,
        net_amount REAL,
        received INTEGER DEFAULT 0,
        notes TEXT
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
        manual_price_tracking INTEGER DEFAULT 0,
        pays_dividend INTEGER DEFAULT 0,
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

    CREATE TABLE IF NOT EXISTS user_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        date_format TEXT DEFAULT 'DD/MM/YYYY',
        finnhub_api_key TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS manual_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        date TEXT NOT NULL,
        price REAL NOT NULL,
        currency TEXT DEFAULT 'EUR',
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ticker, date)
    );

    CREATE TABLE IF NOT EXISTS figi_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_type TEXT NOT NULL,
        query_value TEXT NOT NULL,
        ticker TEXT,
        name TEXT,
        exch_code TEXT,
        security_type TEXT,
        market_sector TEXT,
        cached_at TEXT NOT NULL,
        UNIQUE(query_type, query_value, ticker)
    );

    CREATE TABLE IF NOT EXISTS saxo_price_cache (
        ticker TEXT PRIMARY KEY,
        saxo_price REAL,
        saxo_change_percent REAL,
        currency TEXT,
        updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS broker_cash_balances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        broker_name TEXT NOT NULL,
        currency TEXT NOT NULL DEFAULT 'EUR',
        balance REAL NOT NULL DEFAULT 0,
        UNIQUE(broker_name, currency)
    );

    CREATE TABLE IF NOT EXISTS stock_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        alert_type TEXT NOT NULL,
        period TEXT,
        threshold_price REAL,
        enabled INTEGER DEFAULT 1,
        last_triggered_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    INSERT OR IGNORE INTO user_settings (id, date_format) VALUES (1, 'DD/MM/YYYY');
    """)

    # Add finnhub_api_key column if it doesn't exist
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(user_settings)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'finnhub_api_key' not in columns:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN finnhub_api_key TEXT")
    if 'openfigi_api_key' not in columns:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN openfigi_api_key TEXT")
    if 'saxo_access_token' not in columns:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN saxo_access_token TEXT")
    if 'saxo_refresh_token' not in columns:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN saxo_refresh_token TEXT")
    if 'saxo_token_expiry' not in columns:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN saxo_token_expiry TEXT")
    if 'saxo_client_id' not in columns:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN saxo_client_id TEXT")
    if 'saxo_client_secret' not in columns:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN saxo_client_secret TEXT")
    if 'saxo_redirect_uri' not in columns:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN saxo_redirect_uri TEXT")
    if 'saxo_environment' not in columns:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN saxo_environment TEXT DEFAULT 'SIM'")
    if 'saxo_auth_url' not in columns:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN saxo_auth_url TEXT")
    if 'saxo_token_url' not in columns:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN saxo_token_url TEXT")
    # Add Telegram columns
    if 'telegram_bot_token' not in columns:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN telegram_bot_token TEXT")
    if 'telegram_chat_id' not in columns:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN telegram_chat_id TEXT")

    # Add IBKR Flex Query columns
    if 'ibkr_flex_token' not in columns:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN ibkr_flex_token TEXT")
    if 'ibkr_query_id' not in columns:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN ibkr_query_id TEXT")
    if 'ibkr_last_sync' not in columns:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN ibkr_last_sync TEXT")

    # Add source_id column to transactions for dedup
    cursor.execute("PRAGMA table_info(transactions)")
    tx_columns = [col[1] for col in cursor.fetchall()]
    if 'source_id' not in tx_columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN source_id TEXT")

    # Add source_id column to dividends for dedup
    cursor.execute("PRAGMA table_info(dividends)")
    div_cols_check = [col[1] for col in cursor.fetchall()]
    if 'source_id' not in div_cols_check:
        cursor.execute("ALTER TABLE dividends ADD COLUMN source_id TEXT")

    # Add source_id column to cash_transactions for dedup
    cursor.execute("PRAGMA table_info(cash_transactions)")
    cash_cols_check = [col[1] for col in cursor.fetchall()]
    if 'source_id' not in cash_cols_check:
        cursor.execute("ALTER TABLE cash_transactions ADD COLUMN source_id TEXT")

    # Add cash_balance and cash_currency columns to broker_settings if they don't exist
    cursor.execute("PRAGMA table_info(broker_settings)")
    broker_columns = [col[1] for col in cursor.fetchall()]
    if 'cash_balance' not in broker_columns:
        cursor.execute("ALTER TABLE broker_settings ADD COLUMN cash_balance REAL DEFAULT 0")
    if 'cash_currency' not in broker_columns:
        cursor.execute("ALTER TABLE broker_settings ADD COLUMN cash_currency TEXT DEFAULT 'EUR'")

    # Migrate existing cash data from broker_settings to broker_cash_balances
    cursor.execute("SELECT COUNT(*) FROM broker_cash_balances")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT OR IGNORE INTO broker_cash_balances (broker_name, currency, balance)
            SELECT broker_name, COALESCE(cash_currency, 'EUR'), COALESCE(cash_balance, 0)
            FROM broker_settings
            WHERE COALESCE(cash_balance, 0) != 0
        """)

    # Add account_type column to broker_settings if it doesn't exist
    cursor.execute("PRAGMA table_info(broker_settings)")
    broker_columns2 = [col[1] for col in cursor.fetchall()]
    if 'account_type' not in broker_columns2:
        cursor.execute("ALTER TABLE broker_settings ADD COLUMN account_type TEXT DEFAULT 'Privé'")

    # Add pays_dividend column to stock_info if it doesn't exist
    cursor.execute("PRAGMA table_info(stock_info)")
    stock_columns = [col[1] for col in cursor.fetchall()]
    if 'pays_dividend' not in stock_columns:
        cursor.execute("ALTER TABLE stock_info ADD COLUMN pays_dividend INTEGER DEFAULT 0")

    # Rename old dividend columns if they exist (from earlier schema version)
    cursor.execute("PRAGMA table_info(dividends)")
    div_columns = [col[1] for col in cursor.fetchall()]
    if 'withheld_amount' in div_columns:
        cursor.execute("ALTER TABLE dividends RENAME COLUMN withheld_amount TO withheld_tax")
    if 'net_received' in div_columns:
        cursor.execute("ALTER TABLE dividends RENAME COLUMN net_received TO net_amount")

    # Create indexes for frequently queried columns
    conn.executescript("""
    CREATE INDEX IF NOT EXISTS idx_transactions_ticker ON transactions(ticker);
    CREATE INDEX IF NOT EXISTS idx_transactions_source_id ON transactions(source_id);
    CREATE INDEX IF NOT EXISTS idx_transactions_broker ON transactions(broker);
    CREATE INDEX IF NOT EXISTS idx_dividends_ticker ON dividends(ticker);
    CREATE INDEX IF NOT EXISTS idx_dividends_source_id ON dividends(source_id);
    CREATE INDEX IF NOT EXISTS idx_dividends_ex_date ON dividends(ex_date);
    CREATE INDEX IF NOT EXISTS idx_cash_transactions_source_id ON cash_transactions(source_id);
    CREATE INDEX IF NOT EXISTS idx_stock_alerts_ticker ON stock_alerts(ticker);
    CREATE INDEX IF NOT EXISTS idx_stock_alerts_enabled ON stock_alerts(ticker, enabled);
    CREATE INDEX IF NOT EXISTS idx_price_cache_ticker ON price_cache(ticker);
    CREATE INDEX IF NOT EXISTS idx_stock_info_isin ON stock_info(isin);
    """)

    conn.commit()


# Transaction operations
def insert_transaction(conn, data: dict) -> int:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (
            date, broker, transaction_type, name, ticker, isin,
            quantity, price_per_share, currency, fees, taxes,
            exchange_rate, fees_currency, notes, source_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['date'], data['broker'], data['transaction_type'],
        data['name'], data['ticker'], data['isin'],
        data['quantity'], data['price_per_share'], data['currency'],
        data['fees'], data['taxes'], data['exchange_rate'],
        data['fees_currency'], data.get('notes'), data.get('source_id')
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


def update_transaction(conn, transaction_id: int, data: dict) -> bool:
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE transactions SET
            date = ?, broker = ?, transaction_type = ?, name = ?, ticker = ?, isin = ?,
            quantity = ?, price_per_share = ?, currency = ?, fees = ?, taxes = ?,
            exchange_rate = ?, fees_currency = ?, notes = ?
        WHERE id = ?
    """, (
        data['date'], data['broker'], data['transaction_type'],
        data['name'], data['ticker'], data['isin'],
        data['quantity'], data['price_per_share'], data['currency'],
        data['fees'], data['taxes'], data['exchange_rate'],
        data['fees_currency'], data.get('notes'),
        transaction_id
    ))
    conn.commit()
    return cursor.rowcount > 0


# Dividend operations
def insert_dividend(conn, data: dict) -> int:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO dividends (
            ticker, isin, ex_date, bruto_amount, currency,
            withheld_tax, net_amount, received, notes, source_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['ticker'], data['isin'], data['ex_date'],
        data['bruto_amount'], data['currency'],
        data.get('withheld_tax', 0),
        data.get('net_amount'),
        1 if data.get('received') else 0,
        data.get('notes'),
        data.get('source_id')
    ))
    conn.commit()
    return cursor.lastrowid


def get_all_dividends(conn, ticker: str = None):
    cursor = conn.cursor()
    if ticker:
        cursor.execute(
            """SELECT d.*, s.name as stock_name
               FROM dividends d
               LEFT JOIN stock_info s ON d.ticker = s.ticker
               WHERE d.ticker = ?
               ORDER BY d.ex_date DESC""",
            (ticker,)
        )
    else:
        cursor.execute(
            """SELECT d.*, s.name as stock_name
               FROM dividends d
               LEFT JOIN stock_info s ON d.ticker = s.ticker
               ORDER BY d.ex_date DESC"""
        )
    return [dict(row) for row in cursor.fetchall()]


def delete_dividend(conn, dividend_id: int):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dividends WHERE id = ?", (dividend_id,))
    conn.commit()
    return cursor.rowcount > 0


def update_dividend(conn, dividend_id: int, data: dict) -> bool:
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE dividends SET
            ticker = ?, isin = ?, ex_date = ?, bruto_amount = ?, currency = ?,
            withheld_tax = ?, net_amount = ?, received = ?, notes = ?
        WHERE id = ?
    """, (
        data['ticker'], data['isin'], data['ex_date'],
        data['bruto_amount'], data['currency'],
        data.get('withheld_tax', 0),
        data.get('net_amount'),
        1 if data.get('received') else 0,
        data.get('notes'),
        dividend_id
    ))
    conn.commit()
    return cursor.rowcount > 0


# Cash transaction operations
def insert_cash_transaction(conn, data: dict) -> int:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cash_transactions (
            date, broker, transaction_type, amount, currency,
            source_amount, source_currency, exchange_rate, notes, source_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['date'], data['broker'], data['transaction_type'],
        data['amount'], data['currency'],
        data.get('source_amount'), data.get('source_currency'),
        data.get('exchange_rate'), data.get('notes'), data.get('source_id')
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


def update_broker_account_type(conn, broker_name: str, account_type: str):
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE broker_settings SET account_type = ?, updated_at = CURRENT_TIMESTAMP
        WHERE broker_name = ?
    """, (account_type, broker_name))
    conn.commit()
    return cursor.rowcount > 0


def get_broker_cash_balances(conn, broker_name: str = None):
    cursor = conn.cursor()
    if broker_name:
        cursor.execute(
            "SELECT * FROM broker_cash_balances WHERE broker_name = ? ORDER BY currency",
            (broker_name,)
        )
    else:
        cursor.execute("SELECT * FROM broker_cash_balances ORDER BY broker_name, currency")
    return [dict(row) for row in cursor.fetchall()]


def upsert_broker_cash_balance(conn, broker_name: str, currency: str, balance: float):
    cursor = conn.cursor()
    if balance == 0:
        cursor.execute(
            "DELETE FROM broker_cash_balances WHERE broker_name = ? AND currency = ?",
            (broker_name, currency)
        )
    else:
        cursor.execute("""
            INSERT INTO broker_cash_balances (broker_name, currency, balance)
            VALUES (?, ?, ?)
            ON CONFLICT(broker_name, currency) DO UPDATE SET balance = excluded.balance
        """, (broker_name, currency, balance))
    conn.commit()


def delete_broker_cash_balance(conn, broker_name: str, currency: str):
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM broker_cash_balances WHERE broker_name = ? AND currency = ?",
        (broker_name, currency)
    )
    conn.commit()
    return cursor.rowcount > 0


# Stock info operations
def get_stock_info(conn, ticker: str):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stock_info WHERE ticker = ?", (ticker,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_all_stocks(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stock_info ORDER BY ticker")
    return [dict(row) for row in cursor.fetchall()]


def search_stocks(conn, query: str):
    """Search stocks by ticker, name, or ISIN."""
    cursor = conn.cursor()
    search_term = f"%{query}%"

    # Search in stock_info table
    cursor.execute("""
        SELECT DISTINCT
            ticker, isin, name, asset_type, country, yahoo_ticker, manual_price_tracking
        FROM stock_info
        WHERE ticker LIKE ? OR name LIKE ? OR isin LIKE ?
        ORDER BY
            CASE
                WHEN ticker LIKE ? THEN 1
                WHEN name LIKE ? THEN 2
                ELSE 3
            END,
            name
        LIMIT 20
    """, (search_term, search_term, search_term, f"{query}%", f"{query}%"))

    stock_results = [dict(row) for row in cursor.fetchall()]

    # Also search in transactions for stocks not in stock_info
    cursor.execute("""
        SELECT DISTINCT ticker, isin, name, currency
        FROM transactions
        WHERE (ticker LIKE ? OR name LIKE ? OR isin LIKE ?)
        AND ticker NOT IN (SELECT ticker FROM stock_info)
        ORDER BY name
        LIMIT 10
    """, (search_term, search_term, search_term))

    tx_results = [{
        'ticker': row['ticker'],
        'isin': row['isin'],
        'name': row['name'],
        'asset_type': 'STOCK',
        'country': 'Onbekend',
        'yahoo_ticker': None,
        'manual_price_tracking': 0,
        'from_transactions': True
    } for row in cursor.fetchall()]

    return stock_results + tx_results


def insert_stock_info(conn, data: dict) -> int:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO stock_info (
            ticker, isin, name, asset_type, country,
            custom_dividend_tax_rate, yahoo_ticker, manual_price_tracking, pays_dividend, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['ticker'], data['isin'], data['name'],
        data.get('asset_type', 'STOCK'), data.get('country', 'Verenigde Staten'),
        data.get('custom_dividend_tax_rate'), data.get('yahoo_ticker'),
        1 if data.get('manual_price_tracking') else 0,
        1 if data.get('pays_dividend') else 0,
        data.get('notes')
    ))
    conn.commit()
    return cursor.lastrowid


def update_stock_info(conn, ticker: str, data: dict) -> bool:
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE stock_info SET
            isin = ?, name = ?, asset_type = ?, country = ?,
            custom_dividend_tax_rate = ?, yahoo_ticker = ?,
            manual_price_tracking = ?, pays_dividend = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE ticker = ?
    """, (
        data['isin'], data['name'], data.get('asset_type', 'STOCK'),
        data.get('country', 'Verenigde Staten'),
        data.get('custom_dividend_tax_rate'), data.get('yahoo_ticker'),
        1 if data.get('manual_price_tracking') else 0,
        1 if data.get('pays_dividend') else 0,
        ticker
    ))
    conn.commit()
    return cursor.rowcount > 0


def delete_stock_info(conn, ticker: str) -> bool:
    cursor = conn.cursor()
    cursor.execute("DELETE FROM stock_info WHERE ticker = ?", (ticker,))
    conn.commit()
    return cursor.rowcount > 0


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


# User settings operations
def get_user_settings(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_settings WHERE id = 1")
    row = cursor.fetchone()
    return dict(row) if row else {"id": 1, "date_format": "DD/MM/YYYY"}


def update_user_settings(conn, data: dict) -> bool:
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE user_settings SET
            date_format = ?,
            finnhub_api_key = ?,
            openfigi_api_key = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """, (
        data.get('date_format', 'DD/MM/YYYY'),
        data.get('finnhub_api_key'),
        data.get('openfigi_api_key'),
    ))
    conn.commit()
    return True


# Manual price operations
def insert_manual_price(conn, data: dict) -> int:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO manual_prices (ticker, date, price, currency, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data['ticker'], data['date'], data['price'],
        data.get('currency', 'EUR'), data.get('notes')
    ))
    conn.commit()
    return cursor.lastrowid


def get_manual_prices(conn, ticker: str):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM manual_prices WHERE ticker = ? ORDER BY date DESC",
        (ticker,)
    )
    return [dict(row) for row in cursor.fetchall()]


def get_latest_manual_price(conn, ticker: str):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM manual_prices WHERE ticker = ? ORDER BY date DESC LIMIT 1",
        (ticker,)
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def delete_manual_price(conn, price_id: int):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM manual_prices WHERE id = ?", (price_id,))
    conn.commit()
    return cursor.rowcount > 0


def update_manual_price(conn, price_id: int, data: dict) -> bool:
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE manual_prices SET
            date = ?, price = ?, currency = ?, notes = ?
        WHERE id = ?
    """, (
        data['date'], data['price'],
        data.get('currency', 'EUR'), data.get('notes'),
        price_id
    ))
    conn.commit()
    return cursor.rowcount > 0


def get_figi_cache(conn, query_type: str, query_value: str):
    """Return cached OpenFIGI results if less than 7 days old."""
    from datetime import datetime, timedelta
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    cursor.execute("""
        SELECT ticker, name, exch_code, security_type, market_sector
        FROM figi_cache
        WHERE query_type = ? AND query_value = ? AND cached_at > ?
    """, (query_type, query_value, cutoff))
    return [dict(row) for row in cursor.fetchall()]


def save_figi_cache(conn, query_type: str, query_value: str, results: list):
    """Save OpenFIGI results to cache."""
    from datetime import datetime
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    for r in results:
        cursor.execute("""
            INSERT OR REPLACE INTO figi_cache
                (query_type, query_value, ticker, name, exch_code, security_type, market_sector, cached_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            query_type, query_value,
            r.get('ticker'), r.get('name'), r.get('exch_code'),
            r.get('security_type'), r.get('market_sector'), now
        ))
    conn.commit()


def get_stocks_missing_yahoo_ticker(conn):
    """Get stocks that have an ISIN but no yahoo_ticker (and are not manual_price_tracking)."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM stock_info
        WHERE isin IS NOT NULL AND isin != ''
        AND (yahoo_ticker IS NULL OR yahoo_ticker = '')
        AND manual_price_tracking = 0
    """)
    return [dict(row) for row in cursor.fetchall()]


def update_stock_yahoo_ticker(conn, ticker: str, yahoo_ticker: str) -> bool:
    """Update only the yahoo_ticker field for a stock."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE stock_info SET yahoo_ticker = ?, updated_at = CURRENT_TIMESTAMP
        WHERE ticker = ?
    """, (yahoo_ticker, ticker))
    conn.commit()
    return cursor.rowcount > 0


def clear_all_data(conn):
    """Delete all data from data tables, keeping settings and broker config."""
    ALLOWED_TABLES = {
        'transactions',
        'dividends',
        'cash_transactions',
        'stock_info',
        'price_cache',
        'exchange_rate_cache',
        'manual_prices',
        'figi_cache',
        'saxo_price_cache',
    }
    cursor = conn.cursor()
    for table in ALLOWED_TABLES:
        cursor.execute(f"DELETE FROM {table}")
    conn.commit()


# Saxo token operations
def get_saxo_tokens(conn) -> dict:
    """Get all Saxo OAuth tokens."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT saxo_access_token, saxo_refresh_token, saxo_token_expiry FROM user_settings WHERE id = 1"
    )
    row = cursor.fetchone()
    if not row:
        return {}
    return {
        "access_token": row["saxo_access_token"],
        "refresh_token": row["saxo_refresh_token"],
        "expiry": row["saxo_token_expiry"],
    }


def save_saxo_tokens(conn, access_token: str, refresh_token: str, expiry: str):
    """Save all Saxo OAuth tokens."""
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE user_settings SET
            saxo_access_token = ?,
            saxo_refresh_token = ?,
            saxo_token_expiry = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1""",
        (access_token, refresh_token, expiry),
    )
    conn.commit()


def clear_saxo_tokens(conn):
    """Clear all Saxo tokens (disconnect)."""
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE user_settings SET
            saxo_access_token = NULL,
            saxo_refresh_token = NULL,
            saxo_token_expiry = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1"""
    )
    conn.commit()


# Saxo price cache operations
def get_saxo_price_cache(conn, ticker: str):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT saxo_price, saxo_change_percent, currency, updated_at FROM saxo_price_cache WHERE ticker = ?",
        (ticker,)
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def save_saxo_price_cache(conn, ticker: str, price: float, change_pct: float, currency: str):
    from datetime import datetime
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO saxo_price_cache (ticker, saxo_price, saxo_change_percent, currency, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """, (ticker, price, change_pct, currency, datetime.now().isoformat()))
    conn.commit()


def get_all_saxo_price_cache(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM saxo_price_cache")
    return {row['ticker']: dict(row) for row in cursor.fetchall()}


# Saxo configuration operations
def get_saxo_config(conn) -> dict:
    """Get Saxo API configuration."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT saxo_client_id, saxo_client_secret, saxo_redirect_uri, saxo_auth_url, saxo_token_url FROM user_settings WHERE id = 1"
    )
    row = cursor.fetchone()
    if not row:
        return {}
    return {
        "client_id": row["saxo_client_id"] or "",
        "client_secret": row["saxo_client_secret"] or "",
        "redirect_uri": row["saxo_redirect_uri"] or "",
        "auth_url": row["saxo_auth_url"] or "",
        "token_url": row["saxo_token_url"] or "",
    }


def save_saxo_config(conn, client_id: str, client_secret: str, redirect_uri: str, auth_url: str, token_url: str):
    """Save Saxo API configuration."""
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE user_settings SET
            saxo_client_id = ?,
            saxo_client_secret = ?,
            saxo_redirect_uri = ?,
            saxo_auth_url = ?,
            saxo_token_url = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1""",
        (client_id, client_secret, redirect_uri, auth_url, token_url),
    )
    conn.commit()


# IBKR Flex Query operations
def get_ibkr_config(conn) -> dict:
    """Get IBKR Flex Query configuration."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT ibkr_flex_token, ibkr_query_id, ibkr_last_sync FROM user_settings WHERE id = 1"
    )
    row = cursor.fetchone()
    if not row:
        return {}
    return {
        "flex_token": row["ibkr_flex_token"] or "",
        "query_id": row["ibkr_query_id"] or "",
        "last_sync": row["ibkr_last_sync"],
    }


def save_ibkr_config(conn, flex_token: str, query_id: str):
    """Save IBKR Flex Query configuration."""
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE user_settings SET
            ibkr_flex_token = ?,
            ibkr_query_id = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1""",
        (flex_token, query_id),
    )
    conn.commit()


def clear_ibkr_config(conn):
    """Clear all IBKR config (disconnect)."""
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE user_settings SET
            ibkr_flex_token = NULL,
            ibkr_query_id = NULL,
            ibkr_last_sync = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1"""
    )
    conn.commit()


def update_ibkr_last_sync(conn, timestamp: str):
    """Update IBKR last sync timestamp."""
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE user_settings SET ibkr_last_sync = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
        (timestamp,),
    )
    conn.commit()


def check_source_id_exists(conn, table: str, source_id: str) -> bool:
    """Check if a source_id already exists in a table (for dedup)."""
    ALLOWED_TABLES = {"transactions", "dividends", "cash_transactions"}
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Invalid table name: {table}")
    cursor = conn.cursor()
    cursor.execute(f"SELECT 1 FROM {table} WHERE source_id = ?", (source_id,))
    return cursor.fetchone() is not None


# Telegram configuration operations
def get_telegram_config(conn) -> dict:
    """Get Telegram bot configuration."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT telegram_bot_token, telegram_chat_id FROM user_settings WHERE id = 1"
    )
    row = cursor.fetchone()
    if not row:
        return {}
    return {
        "bot_token": row["telegram_bot_token"] or "",
        "chat_id": row["telegram_chat_id"] or "",
    }


def save_telegram_config(conn, bot_token: str, chat_id: str):
    """Save Telegram bot configuration."""
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE user_settings SET
            telegram_bot_token = ?,
            telegram_chat_id = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1""",
        (bot_token, chat_id),
    )
    conn.commit()


def clear_telegram_config(conn):
    """Clear Telegram configuration (disconnect)."""
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE user_settings SET
            telegram_bot_token = NULL,
            telegram_chat_id = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1"""
    )
    conn.commit()


# Stock alert operations
def get_alerts_for_stock(conn, ticker: str):
    """Get all alerts for a specific stock."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM stock_alerts WHERE ticker = ? ORDER BY created_at DESC",
        (ticker,)
    )
    return [dict(row) for row in cursor.fetchall()]


def get_all_enabled_alerts(conn):
    """Get all enabled alerts."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stock_alerts WHERE enabled = 1")
    return [dict(row) for row in cursor.fetchall()]


def insert_alert(conn, data: dict) -> int:
    """Create a new stock alert."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO stock_alerts (ticker, alert_type, period, threshold_price, enabled)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data['ticker'], data['alert_type'],
        data.get('period'), data.get('threshold_price'),
        1 if data.get('enabled', True) else 0,
    ))
    conn.commit()
    return cursor.lastrowid


def update_alert(conn, alert_id: int, data: dict) -> bool:
    """Update an existing alert."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE stock_alerts SET
            alert_type = ?, period = ?, threshold_price = ?, enabled = ?
        WHERE id = ?
    """, (
        data['alert_type'], data.get('period'),
        data.get('threshold_price'),
        1 if data.get('enabled', True) else 0,
        alert_id,
    ))
    conn.commit()
    return cursor.rowcount > 0


def delete_alert(conn, alert_id: int) -> bool:
    """Delete an alert."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM stock_alerts WHERE id = ?", (alert_id,))
    conn.commit()
    return cursor.rowcount > 0


def update_alert_triggered(conn, alert_id: int):
    """Update the last_triggered_at timestamp for an alert."""
    from datetime import datetime
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE stock_alerts SET last_triggered_at = ? WHERE id = ?",
        (datetime.now().isoformat(), alert_id),
    )
    conn.commit()


