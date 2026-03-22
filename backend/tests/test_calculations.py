"""
Tests for backend/app/services/calculations.py

Tests all pure calculation functions for portfolio metrics.
"""
import pytest

from app.services.calculations import (
    calculate_average_price,
    calculate_total_quantity,
    calculate_total_invested,
    calculate_total_fees,
    calculate_current_value,
    calculate_gain_loss,
    calculate_gain_loss_percent,
    convert_currency,
    calculate_total_invested_eur,
    calculate_holding_metrics,
)


# ---------------------------------------------------------------------------
# Helpers to build transaction dicts
# ---------------------------------------------------------------------------

def _buy(qty: float, price: float, fees: float = 0.0,
         currency: str = "EUR", exchange_rate: float = 1.0) -> dict:
    return {
        "transaction_type": "BUY",
        "quantity": qty,
        "price_per_share": price,
        "fees": fees,
        "currency": currency,
        "exchange_rate": exchange_rate,
    }


def _sell(qty: float, price: float, fees: float = 0.0,
          currency: str = "EUR", exchange_rate: float = 1.0) -> dict:
    return {
        "transaction_type": "SELL",
        "quantity": qty,
        "price_per_share": price,
        "fees": fees,
        "currency": currency,
        "exchange_rate": exchange_rate,
    }


# ===========================================================================
# calculate_average_price
# ===========================================================================

class TestCalculateAveragePrice:
    def test_empty_list_returns_zero(self):
        assert calculate_average_price([]) == 0.0

    def test_single_buy(self):
        txs = [_buy(10, 50.0)]
        assert calculate_average_price(txs) == 50.0

    def test_multiple_buys_weighted_average(self):
        # 10 @ 100 + 20 @ 130 = (1000 + 2600) / 30 = 120.0
        txs = [_buy(10, 100.0), _buy(20, 130.0)]
        assert calculate_average_price(txs) == 120.0

    def test_sell_transactions_ignored(self):
        txs = [_buy(10, 50.0), _sell(5, 60.0)]
        # Only BUY counts: 10 @ 50 => avg = 50
        assert calculate_average_price(txs) == 50.0

    def test_only_sells_returns_zero(self):
        txs = [_sell(5, 60.0)]
        assert calculate_average_price(txs) == 0.0

    def test_rounding(self):
        # 3 @ 10.333 = 30.999 / 3 = 10.333 -> rounds to 10.33
        txs = [_buy(3, 10.333)]
        assert calculate_average_price(txs) == 10.33

    def test_fractional_shares(self):
        txs = [_buy(0.5, 200.0), _buy(1.5, 100.0)]
        # (0.5*200 + 1.5*100) / (0.5+1.5) = (100+150)/2 = 125
        assert calculate_average_price(txs) == 125.0


# ===========================================================================
# calculate_total_quantity
# ===========================================================================

class TestCalculateTotalQuantity:
    def test_empty_list(self):
        assert calculate_total_quantity([]) == 0.0

    def test_buys_only(self):
        txs = [_buy(10, 50.0), _buy(5, 60.0)]
        assert calculate_total_quantity(txs) == 15.0

    def test_buy_and_sell_mix(self):
        txs = [_buy(10, 50.0), _sell(3, 55.0)]
        assert calculate_total_quantity(txs) == 7.0

    def test_fractional_shares(self):
        txs = [_buy(0.5, 100.0), _buy(0.3, 110.0)]
        result = calculate_total_quantity(txs)
        assert abs(result - 0.8) < 1e-9

    def test_sell_all(self):
        txs = [_buy(10, 50.0), _sell(10, 55.0)]
        assert calculate_total_quantity(txs) == 0.0

    def test_oversell_negative_quantity(self):
        txs = [_buy(5, 50.0), _sell(8, 55.0)]
        assert calculate_total_quantity(txs) == -3.0


# ===========================================================================
# calculate_total_invested
# ===========================================================================

class TestCalculateTotalInvested:
    def test_empty_list(self):
        assert calculate_total_invested([]) == 0.0

    def test_only_counts_buys(self):
        txs = [_buy(10, 100.0), _sell(5, 120.0)]
        assert calculate_total_invested(txs) == 1000.0

    def test_excludes_fees(self):
        txs = [_buy(10, 100.0, fees=5.0)]
        # Fees NOT included: 10 * 100 = 1000
        assert calculate_total_invested(txs) == 1000.0

    def test_multiple_buys(self):
        txs = [_buy(10, 100.0), _buy(5, 200.0)]
        # 10*100 + 5*200 = 2000
        assert calculate_total_invested(txs) == 2000.0

    def test_rounding(self):
        txs = [_buy(3, 33.333)]
        # 3 * 33.333 = 99.999 -> rounds to 100.0
        assert calculate_total_invested(txs) == 100.0


# ===========================================================================
# calculate_total_fees
# ===========================================================================

class TestCalculateTotalFees:
    def test_empty_list(self):
        assert calculate_total_fees([]) == 0.0

    def test_sums_across_all_types(self):
        txs = [_buy(10, 100.0, fees=5.0), _sell(5, 120.0, fees=3.0)]
        assert calculate_total_fees(txs) == 8.0

    def test_missing_fees_field_defaults_to_zero(self):
        txs = [{"transaction_type": "BUY", "quantity": 10, "price_per_share": 100.0}]
        assert calculate_total_fees(txs) == 0.0

    def test_zero_fees(self):
        txs = [_buy(10, 100.0, fees=0.0)]
        assert calculate_total_fees(txs) == 0.0

    def test_rounding(self):
        txs = [_buy(1, 10.0, fees=1.005)]
        # 1.005 rounds to 1.0 (banker's rounding: 0.5 goes to even)
        # Actually ROUND_HALF_UP: 1.005 -> 1.01
        assert calculate_total_fees(txs) == 1.01


# ===========================================================================
# calculate_current_value
# ===========================================================================

class TestCalculateCurrentValue:
    def test_basic(self):
        assert calculate_current_value(10, 50.0) == 500.0

    def test_zero_quantity(self):
        assert calculate_current_value(0, 50.0) == 0.0

    def test_zero_price(self):
        assert calculate_current_value(10, 0.0) == 0.0

    def test_rounding(self):
        assert calculate_current_value(3, 33.333) == 100.0


# ===========================================================================
# calculate_gain_loss
# ===========================================================================

class TestCalculateGainLoss:
    def test_profit(self):
        assert calculate_gain_loss(1500.0, 1000.0) == 500.0

    def test_loss(self):
        assert calculate_gain_loss(800.0, 1000.0) == -200.0

    def test_break_even(self):
        assert calculate_gain_loss(1000.0, 1000.0) == 0.0

    def test_rounding(self):
        assert calculate_gain_loss(100.999, 100.0) == 1.0


# ===========================================================================
# calculate_gain_loss_percent
# ===========================================================================

class TestCalculateGainLossPercent:
    def test_positive(self):
        assert calculate_gain_loss_percent(500.0, 1000.0) == 50.0

    def test_negative(self):
        assert calculate_gain_loss_percent(-200.0, 1000.0) == -20.0

    def test_zero_invested_division_by_zero_guard(self):
        assert calculate_gain_loss_percent(500.0, 0.0) == 0.0

    def test_zero_gain(self):
        assert calculate_gain_loss_percent(0.0, 1000.0) == 0.0

    def test_small_percentage(self):
        # 1 / 10000 * 100 = 0.01
        assert calculate_gain_loss_percent(1.0, 10000.0) == 0.01


# ===========================================================================
# convert_currency
# ===========================================================================

class TestConvertCurrency:
    def test_standard_conversion(self):
        # 100 USD * 0.92 = 92.0 EUR
        assert convert_currency(100.0, 0.92) == 92.0

    def test_rate_of_one(self):
        assert convert_currency(100.0, 1.0) == 100.0

    def test_zero_amount(self):
        assert convert_currency(0.0, 0.92) == 0.0

    def test_rounding(self):
        # 100 * 1.2345 = 123.45
        assert convert_currency(100.0, 1.2345) == 123.45


# ===========================================================================
# calculate_total_invested_eur
# ===========================================================================

class TestCalculateTotalInvestedEur:
    def test_eur_transactions(self):
        txs = [_buy(10, 100.0, currency="EUR")]
        assert calculate_total_invested_eur(txs) == 1000.0

    def test_usd_transactions_with_exchange_rate(self):
        # 10 @ 100 USD * 0.92 = 920 EUR
        txs = [_buy(10, 100.0, currency="USD", exchange_rate=0.92)]
        assert calculate_total_invested_eur(txs) == 920.0

    def test_mixed_currencies(self):
        txs = [
            _buy(10, 100.0, currency="EUR"),       # 1000 EUR
            _buy(5, 200.0, currency="USD", exchange_rate=0.90),  # 5*200*0.90 = 900 EUR
        ]
        assert calculate_total_invested_eur(txs) == 1900.0

    def test_sell_ignored(self):
        txs = [
            _buy(10, 100.0, currency="EUR"),
            _sell(5, 120.0, currency="EUR"),
        ]
        assert calculate_total_invested_eur(txs) == 1000.0

    def test_missing_exchange_rate_defaults_to_one(self):
        txs = [{
            "transaction_type": "BUY",
            "quantity": 10,
            "price_per_share": 100.0,
            "currency": "USD",
            # no exchange_rate key
        }]
        # defaults to 1.0 -> 10 * 100 * 1.0 = 1000
        assert calculate_total_invested_eur(txs) == 1000.0

    def test_empty_list(self):
        assert calculate_total_invested_eur([]) == 0.0


# ===========================================================================
# calculate_holding_metrics (integration)
# ===========================================================================

class TestCalculateHoldingMetrics:
    def test_basic_eur_holding(self):
        txs = [_buy(10, 100.0, fees=5.0, currency="EUR")]
        result = calculate_holding_metrics(txs, current_price=120.0)

        assert result["quantity"] == 10.0
        assert result["avg_purchase_price"] == 100.0
        assert result["total_invested"] == 1000.0
        assert result["total_invested_eur"] == 1000.0
        assert result["total_fees"] == 5.0
        assert result["current_price"] == 120.0
        assert result["current_value"] == 1200.0
        assert result["gain_loss"] == 200.0
        assert result["gain_loss_percent"] == 20.0
        assert result["is_usd_account"] is False

    def test_no_current_price(self):
        txs = [_buy(10, 100.0, currency="EUR")]
        result = calculate_holding_metrics(txs, current_price=None)

        assert result["quantity"] == 10.0
        assert result["current_value"] is None
        assert result["gain_loss"] is None
        assert result["gain_loss_percent"] is None

    def test_zero_quantity_no_value(self):
        txs = [_buy(10, 100.0, currency="EUR"), _sell(10, 120.0, currency="EUR")]
        result = calculate_holding_metrics(txs, current_price=120.0)

        assert result["quantity"] == 0.0
        assert result["current_value"] is None
        assert result["gain_loss"] is None

    def test_usd_account_flag(self):
        """USD transactions with exchange_rate=1.0 are treated as USD-only."""
        txs = [_buy(10, 100.0, currency="USD", exchange_rate=1.0)]
        result = calculate_holding_metrics(txs, current_price=110.0)

        assert result["is_usd_account"] is True
        # Gain/loss calculated in USD (no EUR conversion)
        assert result["current_value"] == 1100.0
        assert result["gain_loss"] == 100.0
        assert result["gain_loss_percent"] == 10.0

    def test_usd_with_exchange_rate_converts_to_eur(self):
        """USD transactions with actual exchange_rate are converted to EUR."""
        txs = [_buy(10, 100.0, currency="USD", exchange_rate=0.90)]
        result = calculate_holding_metrics(txs, current_price=110.0, exchange_rate=0.92)

        assert result["is_usd_account"] is False
        # current_value = 10 * 110 = 1100 USD, then * 0.92 = 1012.0 EUR
        assert result["current_value"] == 1012.0
        # total_invested_eur = 10 * 100 * 0.90 = 900 EUR
        assert result["total_invested_eur"] == 900.0
        assert result["gain_loss"] == 112.0
        assert result["gain_loss_percent"] == 12.44

    def test_empty_transactions(self):
        result = calculate_holding_metrics([], current_price=100.0)
        assert result["quantity"] == 0.0
        assert result["current_value"] is None
        # With empty transactions, first_tx is None so is_usd_account
        # short-circuits to None (falsy)
        assert not result["is_usd_account"]
