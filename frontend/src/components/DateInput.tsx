import { useState, useEffect } from 'react';
import { getDateFormat } from '@/utils/formatting';

interface DateInputProps {
  value: string; // ISO format YYYY-MM-DD
  onChange: (value: string) => void;
  className?: string;
}

export default function DateInput({ value, onChange, className = '' }: DateInputProps) {
  const dateFormat = getDateFormat();
  const [displayValue, setDisplayValue] = useState('');

  // Convert ISO to display format
  useEffect(() => {
    if (value) {
      const [year, month, day] = value.split('-');
      if (year && month && day) {
        if (dateFormat === 'DD/MM/YYYY') {
          setDisplayValue(`${day}/${month}/${year}`);
        } else if (dateFormat === 'MM/DD/YYYY') {
          setDisplayValue(`${month}/${day}/${year}`);
        } else {
          setDisplayValue(value); // YYYY-MM-DD
        }
      }
    } else {
      setDisplayValue('');
    }
  }, [value, dateFormat]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const input = e.target.value;
    setDisplayValue(input);

    // Try to parse and convert to ISO
    let iso = '';

    if (dateFormat === 'DD/MM/YYYY') {
      const match = input.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
      if (match) {
        const [, day, month, year] = match;
        iso = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
      }
    } else if (dateFormat === 'MM/DD/YYYY') {
      const match = input.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
      if (match) {
        const [, month, day, year] = match;
        iso = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
      }
    } else {
      // YYYY-MM-DD
      const match = input.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
      if (match) {
        const [, year, month, day] = match;
        iso = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
      }
    }

    if (iso) {
      onChange(iso);
    }
  };

  const getPlaceholder = () => {
    if (dateFormat === 'DD/MM/YYYY') return 'dd/mm/yyyy';
    if (dateFormat === 'MM/DD/YYYY') return 'mm/dd/yyyy';
    return 'yyyy-mm-dd';
  };

  return (
    <input
      type="text"
      value={displayValue}
      onChange={handleChange}
      placeholder={getPlaceholder()}
      className={`${className} w-full px-3 py-2 border rounded-md bg-background`}
    />
  );
}
