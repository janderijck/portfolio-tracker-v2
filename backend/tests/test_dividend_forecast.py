"""
Tests for backend/app/services/dividend_forecast.py

Tests pure forecast functions for dividend calendar.
"""
import pytest
from datetime import date, timedelta
from unittest.mock import patch

from app.services.dividend_forecast import (
    detect_dividend_frequency,
    estimate_next_dividend_amount,
    project_future_ex_dates,
)


# ===========================================================================
# detect_dividend_frequency
# ===========================================================================

class TestDetectDividendFrequency:
    def test_empty_list_returns_annual(self):
        assert detect_dividend_frequency([]) == "annual"

    def test_single_date_returns_annual(self):
        assert detect_dividend_frequency([date(2025, 3, 15)]) == "annual"

    def test_quarterly_dates(self):
        dates = [
            date(2025, 1, 15),
            date(2025, 4, 15),
            date(2025, 7, 15),
            date(2025, 10, 15),
        ]
        assert detect_dividend_frequency(dates) == "quarterly"

    def test_monthly_dates(self):
        dates = [date(2025, m, 15) for m in range(1, 7)]
        assert detect_dividend_frequency(dates) == "monthly"

    def test_annual_dates(self):
        dates = [date(2023, 6, 15), date(2024, 6, 15)]
        assert detect_dividend_frequency(dates) == "annual"

    def test_semi_annual_dates(self):
        dates = [
            date(2024, 3, 15),
            date(2024, 9, 15),
            date(2025, 3, 15),
        ]
        assert detect_dividend_frequency(dates) == "semi-annual"

    def test_unsorted_dates_are_sorted_internally(self):
        # Provide dates out of order; should still detect quarterly
        dates = [
            date(2025, 10, 15),
            date(2025, 1, 15),
            date(2025, 7, 15),
            date(2025, 4, 15),
        ]
        assert detect_dividend_frequency(dates) == "quarterly"

    def test_two_dates_close_together_is_monthly(self):
        dates = [date(2025, 1, 1), date(2025, 1, 28)]
        assert detect_dividend_frequency(dates) == "monthly"


# ===========================================================================
# estimate_next_dividend_amount
# ===========================================================================

class TestEstimateNextDividendAmount:
    def test_with_yf_rate_quarterly(self):
        # yf annual rate = 4.0, quarterly => 4.0 / 4 = 1.0
        result = estimate_next_dividend_amount(
            historical_amounts=[0.9, 0.95, 1.0, 1.05],
            yf_dividend_rate=4.0,
            frequency="quarterly",
        )
        assert result == 1.0

    def test_with_yf_rate_monthly(self):
        result = estimate_next_dividend_amount(
            historical_amounts=[],
            yf_dividend_rate=12.0,
            frequency="monthly",
        )
        assert result == 1.0

    def test_with_yf_rate_annual(self):
        result = estimate_next_dividend_amount(
            historical_amounts=[],
            yf_dividend_rate=2.5,
            frequency="annual",
        )
        assert result == 2.5

    def test_without_yf_rate_falls_back_to_average(self):
        # No yf rate, quarterly -> average last 4 amounts
        result = estimate_next_dividend_amount(
            historical_amounts=[1.0, 1.0, 1.0, 2.0],
            yf_dividend_rate=None,
            frequency="quarterly",
        )
        assert result == 1.25

    def test_without_yf_rate_fewer_history_than_payments(self):
        # Only 2 history entries, quarterly wants 4 -> uses last 2
        result = estimate_next_dividend_amount(
            historical_amounts=[1.0, 3.0],
            yf_dividend_rate=None,
            frequency="quarterly",
        )
        assert result == 2.0

    def test_empty_history_and_no_yf_rate(self):
        result = estimate_next_dividend_amount(
            historical_amounts=[],
            yf_dividend_rate=None,
            frequency="quarterly",
        )
        assert result == 0.0

    def test_yf_rate_zero_falls_back(self):
        # yf rate of 0 is falsy, should fall back to average
        result = estimate_next_dividend_amount(
            historical_amounts=[2.0, 4.0],
            yf_dividend_rate=0.0,
            frequency="annual",
        )
        # annual -> last 1 amount -> 4.0
        assert result == 4.0

    def test_yf_rate_negative_falls_back(self):
        # Negative rate treated as falsy
        result = estimate_next_dividend_amount(
            historical_amounts=[3.0],
            yf_dividend_rate=-1.0,
            frequency="annual",
        )
        assert result == 3.0


# ===========================================================================
# project_future_ex_dates
# ===========================================================================

class TestProjectFutureExDates:
    def test_quarterly_projection(self):
        today = date.today()
        # Last ex-date is 91 days ago (one gap back) so next is around today
        last_ex = today - timedelta(days=91)
        projected = project_future_ex_dates(last_ex, "quarterly", months_ahead=12)

        # Should have roughly 4 quarterly dates in the next 12 months
        assert len(projected) >= 3
        assert len(projected) <= 5
        # All dates should be in the future
        for d in projected:
            assert d > today

    def test_monthly_projection(self):
        today = date.today()
        last_ex = today - timedelta(days=15)
        projected = project_future_ex_dates(last_ex, "monthly", months_ahead=6)

        # Monthly for 6 months should yield ~6 dates
        assert len(projected) >= 5
        assert len(projected) <= 7
        for d in projected:
            assert d > today

    def test_no_dates_in_the_past(self):
        today = date.today()
        # Last ex-date far in the past - projected dates should skip past dates
        last_ex = today - timedelta(days=500)
        projected = project_future_ex_dates(last_ex, "annual", months_ahead=12)

        for d in projected:
            assert d > today

    def test_empty_result_when_horizon_too_short(self):
        today = date.today()
        # Last ex-date is today, annual frequency, 1 month ahead
        # Next date would be ~365 days out, beyond 30-day horizon
        last_ex = today
        projected = project_future_ex_dates(last_ex, "annual", months_ahead=1)
        assert projected == []

    def test_dates_are_sorted(self):
        today = date.today()
        last_ex = today - timedelta(days=30)
        projected = project_future_ex_dates(last_ex, "monthly", months_ahead=6)

        for i in range(len(projected) - 1):
            assert projected[i] < projected[i + 1]

    def test_semi_annual_projection(self):
        today = date.today()
        last_ex = today - timedelta(days=91)
        projected = project_future_ex_dates(last_ex, "semi-annual", months_ahead=18)

        # Semi-annual for 18 months should yield ~2-3 dates
        assert len(projected) >= 2
        assert len(projected) <= 4
        for d in projected:
            assert d > today
