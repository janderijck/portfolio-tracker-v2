import yfinance as yf
from typing import Optional
from .database import get_db, get_cached_exchange_rate, save_exchange_rate_to_cache


def get_current_exchange_rate(from_currency: str = 'USD', to_currency: str = 'EUR') -> float:
    """Get exchange rate from yfinance with caching."""
    if from_currency == to_currency:
        return 1.0

    # Check cache first
    with get_db() as conn:
        cached = get_cached_exchange_rate(conn, from_currency, to_currency)
        if cached:
            return cached

    # Fetch from yfinance
    try:
        ticker_symbol = f"{from_currency}{to_currency}=X"
        ticker = yf.Ticker(ticker_symbol)
        data = ticker.history(period="1d")

        if not data.empty:
            rate = float(data['Close'].iloc[-1])
        else:
            # Try inverse
            ticker_symbol = f"{to_currency}{from_currency}=X"
            ticker = yf.Ticker(ticker_symbol)
            data = ticker.history(period="1d")
            if not data.empty:
                rate = 1 / float(data['Close'].iloc[-1])
            else:
                rate = 1.0

        # Cache the rate
        with get_db() as conn:
            save_exchange_rate_to_cache(conn, from_currency, to_currency, rate)

        return rate
    except Exception:
        return 1.0


def get_current_price(ticker: str) -> Optional[dict]:
    """Fetch current price from yfinance."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='5d')

        if hist.empty:
            return None

        current_price = float(hist['Close'].iloc[-1])
        prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
        change_percent = ((current_price - prev_close) / prev_close) * 100 if prev_close else 0

        info = stock.info
        currency = info.get('currency', 'USD')

        return {
            'current_price': current_price,
            'change_percent': change_percent,
            'currency': currency
        }
    except Exception:
        return None


class TaxCalculator:
    """Calculate dividend taxes based on broker and stock configuration."""

    def __init__(self, conn):
        self.conn = conn

    def get_broker_w8_status(self, broker: str) -> bool:
        """Check if broker has W-8BEN signed."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT has_w8ben FROM broker_settings WHERE broker_name = ?",
            (broker,)
        )
        result = cursor.fetchone()
        return bool(result['has_w8ben']) if result else False

    def get_stock_info(self, ticker: str) -> Optional[dict]:
        """Get stock info for tax calculation."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT asset_type, country, custom_dividend_tax_rate FROM stock_info WHERE ticker = ?",
            (ticker,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None

    def calculate_tax(
        self,
        bruto_amount: float,
        ticker: str,
        broker: str,
        us_withholding_override: Optional[float] = None,
        belgian_tax_override: Optional[float] = None
    ) -> dict:
        """Calculate dividend tax breakdown."""

        # Get stock info
        stock_info = self.get_stock_info(ticker)
        has_w8ben = self.get_broker_w8_status(broker)

        # Determine US withholding tax
        if us_withholding_override is not None:
            us_withholding = us_withholding_override
        elif stock_info and stock_info.get('country') == 'Verenigde Staten':
            us_rate = 0.15 if has_w8ben else 0.30
            us_withholding = bruto_amount * us_rate
        else:
            us_withholding = 0

        # Determine Belgian tax
        if belgian_tax_override is not None:
            belgian_tax = belgian_tax_override
        elif stock_info and stock_info.get('custom_dividend_tax_rate'):
            belgian_tax = bruto_amount * stock_info['custom_dividend_tax_rate']
        elif stock_info and stock_info.get('asset_type') == 'REIT':
            belgian_tax = bruto_amount * 0.489  # 48.9% for REITs
        else:
            belgian_tax = bruto_amount * 0.30  # Standard 30%

        total_tax = us_withholding + belgian_tax
        net_amount = bruto_amount - total_tax
        effective_rate = (total_tax / bruto_amount * 100) if bruto_amount > 0 else 0

        # Create breakdown string
        breakdown_parts = []
        if us_withholding > 0:
            us_rate = (us_withholding / bruto_amount * 100) if bruto_amount > 0 else 0
            breakdown_parts.append(f"US: {us_rate:.1f}% (€{us_withholding:.2f})")
        if belgian_tax > 0:
            be_rate = (belgian_tax / bruto_amount * 100) if bruto_amount > 0 else 0
            breakdown_parts.append(f"BE: {be_rate:.1f}% (€{belgian_tax:.2f})")

        breakdown = " + ".join(breakdown_parts) if breakdown_parts else "Geen belasting"

        return {
            'bruto_amount': bruto_amount,
            'us_withholding': us_withholding,
            'belgian_tax': belgian_tax,
            'total_tax': total_tax,
            'net_amount': net_amount,
            'effective_rate': effective_rate,
            'breakdown': breakdown
        }


def calculate_portfolio_performance(
    avg_purchase_price_eur: float,
    current_price: float,
    quantity: int,
    currency: str = 'EUR',
    exchange_rate: float = 1.0,
    dividends_netto: float = 0
) -> dict:
    """Calculate portfolio performance metrics."""

    total_invested = avg_purchase_price_eur * quantity

    # Convert current price to EUR
    if currency != 'EUR' and exchange_rate:
        current_price_eur = current_price * exchange_rate
    else:
        current_price_eur = current_price

    current_value = current_price_eur * quantity

    gain_loss_excl_div = current_value - total_invested
    gain_loss_incl_div = gain_loss_excl_div + dividends_netto
    gain_loss_percent = (gain_loss_incl_div / total_invested * 100) if total_invested > 0 else 0

    return {
        'total_invested': total_invested,
        'current_value': current_value,
        'current_price_eur': current_price_eur,
        'gain_loss_excl_div': gain_loss_excl_div,
        'gain_loss_incl_div': gain_loss_incl_div,
        'gain_loss_percent': gain_loss_percent,
        'dividends_netto': dividends_netto
    }


def calculate_dividend_summary(conn, ticker: str) -> dict:
    """Calculate total dividends for a ticker."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            id, bruto_amount, currency, received, tax_paid,
            withheld_amount, additional_tax_due, net_received
        FROM dividends
        WHERE ticker = ? AND received = 1
        ORDER BY ex_date DESC
    """, (ticker,))

    dividends = cursor.fetchall()

    if not dividends:
        return {
            'total_bruto': 0,
            'total_tax': 0,
            'total_netto': 0,
            'count': 0,
            'received_count': 0,
            'currency': 'EUR'
        }

    total_bruto = 0
    total_tax = 0
    total_netto = 0
    currency = 'EUR'

    tax_calc = TaxCalculator(conn)

    # Get broker for this ticker
    cursor.execute("""
        SELECT broker FROM transactions WHERE ticker = ? ORDER BY date DESC LIMIT 1
    """, (ticker,))
    broker_result = cursor.fetchone()
    broker = broker_result['broker'] if broker_result else None

    for div in dividends:
        bruto = div['bruto_amount']
        total_bruto += bruto
        currency = div['currency'] or 'USD'

        # Use manual values if provided
        withheld = div['withheld_amount'] or 0
        additional = div['additional_tax_due'] or 0

        if withheld > 0 or additional > 0 or div['net_received']:
            total_tax += withheld + additional
            if div['net_received']:
                total_netto += div['net_received']
            else:
                total_netto += bruto - withheld - additional
        elif div['tax_paid'] and broker:
            # Calculate tax
            tax_result = tax_calc.calculate_tax(bruto, ticker, broker)
            total_tax += tax_result['total_tax']
            total_netto += tax_result['net_amount']
        else:
            total_netto += bruto

    # Get total count
    cursor.execute("SELECT COUNT(*) FROM dividends WHERE ticker = ?", (ticker,))
    total_count = cursor.fetchone()[0]

    return {
        'total_bruto': total_bruto,
        'total_tax': total_tax,
        'total_netto': total_netto,
        'count': total_count,
        'received_count': len(dividends),
        'currency': currency
    }


def calculate_cash_flow(conn, broker: str = None) -> list:
    """Calculate cash flow summary per broker."""
    cursor = conn.cursor()

    # Get cash transactions
    if broker:
        cursor.execute("""
            SELECT broker,
                SUM(CASE WHEN transaction_type = 'DEPOSIT' THEN
                    COALESCE(source_amount, amount) ELSE 0 END) as deposits,
                SUM(CASE WHEN transaction_type = 'WITHDRAWAL' THEN
                    COALESCE(source_amount, amount) ELSE 0 END) as withdrawals
            FROM cash_transactions
            WHERE broker = ?
            GROUP BY broker
        """, (broker,))
    else:
        cursor.execute("""
            SELECT broker,
                SUM(CASE WHEN transaction_type = 'DEPOSIT' THEN
                    COALESCE(source_amount, amount) ELSE 0 END) as deposits,
                SUM(CASE WHEN transaction_type = 'WITHDRAWAL' THEN
                    COALESCE(source_amount, amount) ELSE 0 END) as withdrawals
            FROM cash_transactions
            GROUP BY broker
        """)

    cash_data = {row['broker']: dict(row) for row in cursor.fetchall()}

    # Get purchases/sales per broker
    cursor.execute("""
        SELECT
            (SELECT broker FROM transactions t2 WHERE t2.ticker = t.ticker
             ORDER BY date DESC LIMIT 1) as broker,
            SUM(CASE WHEN transaction_type = 'BUY' THEN
                quantity * price_per_share + fees ELSE 0 END) as purchases,
            SUM(CASE WHEN transaction_type = 'SELL' THEN
                quantity * price_per_share - fees ELSE 0 END) as sales
        FROM transactions t
        GROUP BY broker
    """)

    tx_data = {row['broker']: dict(row) for row in cursor.fetchall()}

    # Get dividends per broker
    cursor.execute("""
        SELECT
            (SELECT broker FROM transactions WHERE ticker = d.ticker
             ORDER BY date DESC LIMIT 1) as broker,
            SUM(COALESCE(net_received, bruto_amount)) as dividends
        FROM dividends d
        WHERE received = 1
        GROUP BY broker
    """)

    div_data = {row['broker']: row['dividends'] for row in cursor.fetchall()}

    # Combine data
    all_brokers = set(cash_data.keys()) | set(tx_data.keys())
    results = []

    for b in all_brokers:
        cash = cash_data.get(b, {'deposits': 0, 'withdrawals': 0})
        tx = tx_data.get(b, {'purchases': 0, 'sales': 0})
        dividends = div_data.get(b, 0)

        deposits = cash.get('deposits', 0) or 0
        withdrawals = cash.get('withdrawals', 0) or 0
        purchases = tx.get('purchases', 0) or 0
        sales = tx.get('sales', 0) or 0

        expected_cash = deposits - withdrawals - purchases + sales + dividends
        net_deposited = deposits - withdrawals

        results.append({
            'broker': b,
            'deposits': deposits,
            'withdrawals': withdrawals,
            'net_deposited': net_deposited,
            'purchases': purchases,
            'sales': sales,
            'dividends': dividends,
            'expected_cash': expected_cash,
            'portfolio_value': 0,  # To be filled by caller
            'total_value': expected_cash,  # Will add portfolio value
            'currency': 'EUR'
        })

    return results


def calculate_fx_gain_loss(conn, broker: str = None) -> list:
    """Calculate FX gain/loss on currency conversions."""
    cursor = conn.cursor()

    query = """
        SELECT broker, source_currency, currency as dest_currency,
               amount as dest_amount, source_amount, exchange_rate as original_rate
        FROM cash_transactions
        WHERE source_currency IS NOT NULL
        AND source_currency != currency
    """

    if broker:
        query += " AND broker = ?"
        cursor.execute(query, (broker,))
    else:
        cursor.execute(query)

    results = []
    broker_totals = {}

    for row in cursor.fetchall():
        b = row['broker']
        source_curr = row['source_currency']
        dest_curr = row['dest_currency']

        # Get current rate
        current_rate = get_current_exchange_rate(source_curr, dest_curr)

        # Calculate what the original EUR would be worth now
        current_value_eur = row['dest_amount'] / current_rate if current_rate else 0
        gain_loss = current_value_eur - row['source_amount']

        if b not in broker_totals:
            broker_totals[b] = {
                'broker': b,
                'source_currency': source_curr,
                'dest_currency': dest_curr,
                'original_amount': 0,
                'current_value_eur': 0,
                'gain_loss': 0,
                'avg_rate_at_deposit': 0,
                'current_rate': current_rate
            }

        broker_totals[b]['original_amount'] += row['source_amount']
        broker_totals[b]['current_value_eur'] += current_value_eur
        broker_totals[b]['gain_loss'] += gain_loss

    for b, data in broker_totals.items():
        if data['original_amount'] > 0:
            # Calculate weighted average rate
            data['avg_rate_at_deposit'] = data['current_value_eur'] / data['original_amount'] if data['original_amount'] else 0
        results.append(data)

    return results
