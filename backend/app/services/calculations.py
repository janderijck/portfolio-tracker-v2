"""
Pure calculation functions for portfolio metrics.
All functions should be stateless and have no side effects.
"""
from typing import List, Optional
from decimal import Decimal, ROUND_HALF_UP


def calculate_average_price(transactions: List[dict]) -> float:
    """
    Calculate average purchase price from BUY transactions.

    Formula: Σ(quantity × price) / Σ(quantity)
    Fees are NOT included in average price.

    Args:
        transactions: List of transaction dicts with 'transaction_type', 'quantity', 'price_per_share'

    Returns:
        Average price per share, or 0 if no buys
    """
    total_cost = Decimal('0')
    total_quantity = Decimal('0')

    for tx in transactions:
        if tx['transaction_type'] == 'BUY':
            quantity = Decimal(str(tx['quantity']))
            price = Decimal(str(tx['price_per_share']))
            total_cost += quantity * price
            total_quantity += quantity

    if total_quantity == 0:
        return 0.0

    avg = total_cost / total_quantity
    return float(avg.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def calculate_total_quantity(transactions: List[dict]) -> int:
    """
    Calculate net quantity from all transactions.

    Formula: Σ(BUY quantities) - Σ(SELL quantities)

    Args:
        transactions: List of transaction dicts

    Returns:
        Net quantity held
    """
    total = 0
    for tx in transactions:
        if tx['transaction_type'] == 'BUY':
            total += tx['quantity']
        else:  # SELL
            total -= tx['quantity']
    return total


def calculate_total_invested(transactions: List[dict]) -> float:
    """
    Calculate total amount invested from BUY transactions.

    Formula: Σ(quantity × price) for BUY transactions
    Fees are NOT included.

    Args:
        transactions: List of transaction dicts

    Returns:
        Total invested amount
    """
    total = Decimal('0')

    for tx in transactions:
        if tx['transaction_type'] == 'BUY':
            quantity = Decimal(str(tx['quantity']))
            price = Decimal(str(tx['price_per_share']))
            total += quantity * price

    return float(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def calculate_total_fees(transactions: List[dict]) -> float:
    """
    Calculate total fees from all transactions.

    Args:
        transactions: List of transaction dicts with 'fees'

    Returns:
        Total fees paid
    """
    total = Decimal('0')

    for tx in transactions:
        fees = Decimal(str(tx.get('fees', 0)))
        total += fees

    return float(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def calculate_current_value(quantity: int, current_price: float) -> float:
    """
    Calculate current market value.

    Formula: quantity × current_price

    Args:
        quantity: Number of shares held
        current_price: Current market price per share

    Returns:
        Current market value
    """
    value = Decimal(str(quantity)) * Decimal(str(current_price))
    return float(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def calculate_gain_loss(current_value: float, total_invested: float) -> float:
    """
    Calculate gain or loss.

    Formula: current_value - total_invested

    Args:
        current_value: Current market value
        total_invested: Total amount invested

    Returns:
        Gain (positive) or loss (negative)
    """
    result = Decimal(str(current_value)) - Decimal(str(total_invested))
    return float(result.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def calculate_gain_loss_percent(gain_loss: float, total_invested: float) -> float:
    """
    Calculate gain/loss as percentage.

    Formula: (gain_loss / total_invested) × 100

    Args:
        gain_loss: Absolute gain/loss amount
        total_invested: Total amount invested

    Returns:
        Percentage gain/loss, or 0 if no investment
    """
    if total_invested == 0:
        return 0.0

    percent = (Decimal(str(gain_loss)) / Decimal(str(total_invested))) * 100
    return float(percent.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def convert_currency(amount: float, exchange_rate: float) -> float:
    """
    Convert amount using exchange rate.

    Args:
        amount: Amount in source currency
        exchange_rate: Rate to multiply by (e.g., USD to EUR)

    Returns:
        Converted amount
    """
    result = Decimal(str(amount)) * Decimal(str(exchange_rate))
    return float(result.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def calculate_total_invested_eur(transactions: List[dict]) -> float:
    """
    Calculate total invested in EUR, accounting for exchange rates.

    For each BUY transaction:
    - If currency is EUR: use price directly
    - If currency is USD: multiply by exchange_rate stored on transaction

    Args:
        transactions: List of transaction dicts with exchange_rate

    Returns:
        Total invested in EUR
    """
    total = Decimal('0')

    for tx in transactions:
        if tx['transaction_type'] == 'BUY':
            quantity = Decimal(str(tx['quantity']))
            price = Decimal(str(tx['price_per_share']))
            cost = quantity * price

            if tx['currency'] != 'EUR':
                exchange_rate = Decimal(str(tx.get('exchange_rate', 1.0)))
                cost = cost * exchange_rate

            total += cost

    return float(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def calculate_holding_metrics(
    transactions: List[dict],
    current_price: Optional[float],
    exchange_rate: float = 1.0
) -> dict:
    """
    Calculate all metrics for a single holding.

    This is a composition of the individual calculation functions.

    Args:
        transactions: All transactions for this holding
        current_price: Current market price (None if unavailable)
        exchange_rate: Current USD/EUR rate for converting current value

    Returns:
        Dict with all calculated metrics
    """
    quantity = calculate_total_quantity(transactions)
    avg_price = calculate_average_price(transactions)
    total_invested = calculate_total_invested(transactions)
    total_invested_eur = calculate_total_invested_eur(transactions)
    total_fees = calculate_total_fees(transactions)

    # Determine if this is a USD-only position (IBKR USD account)
    first_tx = transactions[0] if transactions else None
    is_usd_account = (
        first_tx and
        first_tx['currency'] == 'USD' and
        first_tx.get('exchange_rate', 1.0) == 1.0
    )

    if current_price and quantity > 0:
        current_value = calculate_current_value(quantity, current_price)

        if is_usd_account:
            # Keep everything in USD
            gain_loss = calculate_gain_loss(current_value, total_invested)
            gain_loss_percent = calculate_gain_loss_percent(gain_loss, total_invested)
        else:
            # Convert to EUR
            current_value_eur = convert_currency(current_value, exchange_rate) if first_tx and first_tx['currency'] == 'USD' else current_value
            gain_loss = calculate_gain_loss(current_value_eur, total_invested_eur)
            gain_loss_percent = calculate_gain_loss_percent(gain_loss, total_invested_eur)
            current_value = current_value_eur
    else:
        current_value = None
        gain_loss = None
        gain_loss_percent = None

    return {
        'quantity': quantity,
        'avg_purchase_price': avg_price,
        'total_invested': total_invested,
        'total_invested_eur': total_invested_eur,
        'total_fees': total_fees,
        'current_price': current_price,
        'current_value': current_value,
        'gain_loss': gain_loss,
        'gain_loss_percent': gain_loss_percent,
        'is_usd_account': is_usd_account,
    }
