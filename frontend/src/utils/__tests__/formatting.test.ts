import { describe, it, expect } from 'vitest';
import {
  getCurrencySymbol,
  formatPercent,
  formatCurrency,
  frequencyLabel,
  formatDate,
} from '../formatting';

describe('getCurrencySymbol', () => {
  it('returns $ for USD', () => {
    expect(getCurrencySymbol('USD')).toBe('$');
  });

  it('returns € for EUR', () => {
    expect(getCurrencySymbol('EUR')).toBe('€');
  });

  it('returns € for GBP (defaults to €)', () => {
    expect(getCurrencySymbol('GBP')).toBe('€');
  });

  it('returns € for CHF (defaults to €)', () => {
    expect(getCurrencySymbol('CHF')).toBe('€');
  });

  it('returns € for unknown currency', () => {
    expect(getCurrencySymbol('JPY')).toBe('€');
  });
});

describe('formatPercent', () => {
  it('formats positive value with + sign', () => {
    expect(formatPercent(5.25)).toBe('+5.25%');
  });

  it('formats negative value with - sign', () => {
    expect(formatPercent(-3.1)).toBe('-3.10%');
  });

  it('formats zero with + sign', () => {
    expect(formatPercent(0)).toBe('+0.00%');
  });

  it('rounds to two decimal places', () => {
    expect(formatPercent(12.3456)).toBe('+12.35%');
  });

  it('pads single decimal to two places', () => {
    expect(formatPercent(1)).toBe('+1.00%');
  });
});

describe('formatCurrency', () => {
  it('formats EUR value with € symbol (default currency)', () => {
    const result = formatCurrency(1234.56);
    expect(result).toBe('€1.234,56');
  });

  it('formats USD value with $ symbol', () => {
    const result = formatCurrency(1234.56, 'USD');
    expect(result).toBe('$1.234,56');
  });

  it('formats EUR value explicitly', () => {
    const result = formatCurrency(99.9, 'EUR');
    expect(result).toBe('€99,90');
  });

  it('formats zero', () => {
    expect(formatCurrency(0)).toBe('€0,00');
  });

  it('formats negative value', () => {
    const result = formatCurrency(-500.5);
    expect(result).toBe('€-500,50');
  });

  it('formats large numbers with thousands separator', () => {
    const result = formatCurrency(1000000);
    expect(result).toBe('€1.000.000,00');
  });

  it('uses € for non-USD currencies', () => {
    const result = formatCurrency(100, 'GBP');
    expect(result).toBe('€100,00');
  });
});

describe('frequencyLabel', () => {
  it('returns Maandelijks for monthly', () => {
    expect(frequencyLabel('monthly')).toBe('Maandelijks');
  });

  it('returns Kwartaal for quarterly', () => {
    expect(frequencyLabel('quarterly')).toBe('Kwartaal');
  });

  it('returns Halfjaarlijks for semi-annual', () => {
    expect(frequencyLabel('semi-annual')).toBe('Halfjaarlijks');
  });

  it('returns Jaarlijks for annual', () => {
    expect(frequencyLabel('annual')).toBe('Jaarlijks');
  });

  it('returns Onregelmatig for irregular', () => {
    expect(frequencyLabel('irregular')).toBe('Onregelmatig');
  });

  it('returns the input string for unknown frequency', () => {
    expect(frequencyLabel('weekly')).toBe('weekly');
  });

  it('returns the input string for empty string', () => {
    expect(frequencyLabel('')).toBe('');
  });
});

describe('formatDate', () => {
  // Using explicit format parameter to avoid localStorage dependency

  it('formats date as DD/MM/YYYY', () => {
    expect(formatDate('2024-06-15', 'DD/MM/YYYY')).toBe('15/06/2024');
  });

  it('formats date as MM/DD/YYYY', () => {
    expect(formatDate('2024-06-15', 'MM/DD/YYYY')).toBe('06/15/2024');
  });

  it('formats date as YYYY-MM-DD', () => {
    expect(formatDate('2024-06-15', 'YYYY-MM-DD')).toBe('2024-06-15');
  });

  it('defaults to DD/MM/YYYY for unknown format', () => {
    expect(formatDate('2024-06-15', 'UNKNOWN')).toBe('15/06/2024');
  });

  it('pads single-digit day and month', () => {
    expect(formatDate('2024-01-05', 'DD/MM/YYYY')).toBe('05/01/2024');
  });

  it('handles end-of-year date', () => {
    expect(formatDate('2024-12-31', 'DD/MM/YYYY')).toBe('31/12/2024');
  });

  it('handles ISO date-time string input', () => {
    expect(formatDate('2024-06-15T10:30:00Z', 'DD/MM/YYYY')).toBe('15/06/2024');
  });
});
