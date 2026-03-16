"""
Pure forecast functions for dividend calendar.

No DB access, no API calls — only calculations.
"""
from datetime import date, timedelta
from statistics import median
from typing import List, Optional


FREQUENCY_GAPS = {
    "monthly": 30,
    "quarterly": 91,
    "semi-annual": 182,
    "annual": 365,
}

PAYMENTS_PER_YEAR = {
    "monthly": 12,
    "quarterly": 4,
    "semi-annual": 2,
    "annual": 1,
}


def detect_dividend_frequency(ex_dates: List[date]) -> str:
    """Detect dividend payment frequency from historical ex-dates.

    Args:
        ex_dates: Sorted list of ex-dividend dates.

    Returns:
        One of "monthly", "quarterly", "semi-annual", "annual".
    """
    if len(ex_dates) < 2:
        return "annual"

    sorted_dates = sorted(ex_dates)
    gaps = [
        (sorted_dates[i + 1] - sorted_dates[i]).days
        for i in range(len(sorted_dates) - 1)
    ]

    median_gap = median(gaps)

    if median_gap < 45:
        return "monthly"
    elif median_gap < 120:
        return "quarterly"
    elif median_gap < 270:
        return "semi-annual"
    else:
        return "annual"


def estimate_next_dividend_amount(
    historical_amounts: List[float],
    yf_dividend_rate: Optional[float],
    frequency: str,
) -> float:
    """Estimate the next per-share dividend amount.

    Prefers yf_dividend_rate / payments_per_year (most reliable).
    Falls back to average of most recent payments.

    Args:
        historical_amounts: List of recent per-share dividend amounts.
        yf_dividend_rate: Annual dividend rate from yfinance info.
        frequency: Detected frequency string.

    Returns:
        Estimated per-share dividend amount for next payment.
    """
    payments = PAYMENTS_PER_YEAR.get(frequency, 1)

    if yf_dividend_rate and yf_dividend_rate > 0:
        return yf_dividend_rate / payments

    if not historical_amounts:
        return 0.0

    recent = historical_amounts[-payments:]
    return sum(recent) / len(recent)


def project_future_ex_dates(
    last_ex_date: date,
    frequency: str,
    months_ahead: int = 12,
) -> List[date]:
    """Project future ex-dividend dates based on frequency.

    Args:
        last_ex_date: Most recent known ex-dividend date.
        frequency: Detected frequency string.
        months_ahead: How many months into the future to project.

    Returns:
        List of projected future ex-dates (only dates in the future).
    """
    gap_days = FREQUENCY_GAPS.get(frequency, 365)
    today = date.today()
    horizon = today + timedelta(days=months_ahead * 30)

    projected = []
    next_date = last_ex_date + timedelta(days=gap_days)

    while next_date <= horizon:
        if next_date > today:
            projected.append(next_date)
        next_date += timedelta(days=gap_days)

    return projected
