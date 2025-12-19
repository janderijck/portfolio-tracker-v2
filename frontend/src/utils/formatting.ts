/**
 * Pure formatting functions for display purposes.
 */

/**
 * Get user's date format preference from localStorage or default.
 */
export function getDateFormat(): string {
  const settings = localStorage.getItem('userSettings');
  if (settings) {
    try {
      const parsed = JSON.parse(settings);
      return parsed.date_format || 'DD/MM/YYYY';
    } catch {
      return 'DD/MM/YYYY';
    }
  }
  return 'DD/MM/YYYY';
}

/**
 * Save user settings to localStorage.
 */
export function saveDateFormat(format: string): void {
  const settings = { date_format: format };
  localStorage.setItem('userSettings', JSON.stringify(settings));
}

/**
 * Format a number as currency with appropriate symbol.
 */
export function formatCurrency(value: number, currency: string = 'EUR'): string {
  const symbol = currency === 'USD' ? '$' : '€';
  return `${symbol}${value.toLocaleString('nl-NL', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`;
}

/**
 * Format a number as percentage with +/- sign.
 */
export function formatPercent(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

/**
 * Format a date string for display based on user preference.
 */
export function formatDate(dateString: string, format?: string): string {
  const date = new Date(dateString);
  const dateFormat = format || getDateFormat();

  const day = date.getDate().toString().padStart(2, '0');
  const month = (date.getMonth() + 1).toString().padStart(2, '0');
  const year = date.getFullYear();

  switch (dateFormat) {
    case 'MM/DD/YYYY':
      return `${month}/${day}/${year}`;
    case 'YYYY-MM-DD':
      return `${year}-${month}-${day}`;
    case 'DD/MM/YYYY':
    default:
      return `${day}/${month}/${year}`;
  }
}

/**
 * Get today's date as ISO string (YYYY-MM-DD).
 */
export function getTodayISO(): string {
  return new Date().toISOString().split('T')[0];
}

/**
 * Get currency symbol for a currency code.
 */
export function getCurrencySymbol(currency: string): string {
  return currency === 'USD' ? '$' : '€';
}

/**
 * Get background color class for manual price based on age.
 * Returns Tailwind background color class based on how old the price is.
 *
 * @param dateString - ISO date string of the manual price
 * @returns Tailwind background color class or empty string
 */
export function getManualPriceAgeColor(dateString: string | null): string {
  if (!dateString) return '';

  const priceDate = new Date(dateString);
  const today = new Date();
  const diffTime = today.getTime() - priceDate.getTime();
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays > 14) {
    return 'bg-red-100 dark:bg-red-900/30';
  } else if (diffDays > 7) {
    return 'bg-orange-100 dark:bg-orange-900/30';
  } else if (diffDays > 1) {
    return 'bg-yellow-100 dark:bg-yellow-900/30';
  }

  return '';
}
