import { useDividends } from '@/hooks/usePortfolio';
import { Loader2 } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

export default function Dividends() {
  const { data: dividends, isLoading, error } = useDividends();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center text-destructive">
        Error loading dividends: {error.message}
      </div>
    );
  }

  if (!dividends) return null;

  const formatCurrency = (value: number, currency: string = 'EUR') => {
    const symbol = currency === 'USD' ? '$' : '€';
    return `${symbol}${value.toLocaleString('nl-NL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  // Group dividends by month for chart
  const monthlyData = dividends.reduce((acc, div) => {
    const month = div.ex_date.substring(0, 7); // YYYY-MM
    if (!acc[month]) {
      acc[month] = { month, gross: 0, net: 0 };
    }
    acc[month].gross += div.bruto_amount;
    acc[month].net += div.net_amount || div.bruto_amount - div.withheld_tax;
    return acc;
  }, {} as Record<string, { month: string; gross: number; net: number }>);

  const chartData = Object.values(monthlyData).sort((a, b) => a.month.localeCompare(b.month));

  // Calculate totals
  const totals = dividends.reduce(
    (acc, div) => ({
      gross: acc.gross + div.bruto_amount,
      withheld: acc.withheld + div.withheld_tax,
      net: acc.net + (div.net_amount || div.bruto_amount - div.withheld_tax),
    }),
    { gross: 0, withheld: 0, net: 0 }
  );

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Dividenden Overzicht</h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-card rounded-lg border p-4">
          <div className="text-sm text-muted-foreground">Totaal Bruto</div>
          <div className="text-xl font-bold mt-1">{formatCurrency(totals.gross)}</div>
        </div>
        <div className="bg-card rounded-lg border p-4">
          <div className="text-sm text-muted-foreground">Ingehouden Belasting</div>
          <div className="text-xl font-bold mt-1 text-red-500">{formatCurrency(totals.withheld)}</div>
        </div>
        <div className="bg-card rounded-lg border p-4">
          <div className="text-sm text-muted-foreground">Totaal Netto</div>
          <div className="text-xl font-bold mt-1 text-green-500">{formatCurrency(totals.net)}</div>
        </div>
      </div>

      {/* Monthly Chart */}
      {chartData.length > 0 && (
        <div className="bg-card rounded-lg border p-6">
          <h3 className="text-lg font-semibold mb-4">Maandelijks Dividend</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip formatter={(value: number) => formatCurrency(value)} />
                <Legend />
                <Bar dataKey="gross" name="Bruto" fill="#8884d8" />
                <Bar dataKey="net" name="Netto" fill="#82ca9d" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Dividends Table */}
      <div className="bg-card rounded-lg border">
        <div className="p-6 border-b">
          <h3 className="text-lg font-semibold">Alle Dividenden</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="text-left p-4 font-medium">Ticker</th>
                <th className="text-left p-4 font-medium">Ex-date</th>
                <th className="text-right p-4 font-medium">Bruto</th>
                <th className="text-right p-4 font-medium">Ingehouden</th>
                <th className="text-right p-4 font-medium">Netto</th>
                <th className="text-center p-4 font-medium">Ontvangen</th>
              </tr>
            </thead>
            <tbody>
              {dividends.map((div) => (
                <tr key={div.id} className="border-b hover:bg-muted/50">
                  <td className="p-4 font-medium">{div.ticker}</td>
                  <td className="p-4">{div.ex_date}</td>
                  <td className="text-right p-4">{formatCurrency(div.bruto_amount, div.currency)}</td>
                  <td className="text-right p-4 text-red-500">{formatCurrency(div.withheld_tax, div.currency)}</td>
                  <td className="text-right p-4 text-green-500">
                    {formatCurrency(div.net_amount || div.bruto_amount - div.withheld_tax, div.currency)}
                  </td>
                  <td className="text-center p-4">
                    <span className={div.received ? 'text-green-500' : 'text-muted-foreground'}>
                      {div.received ? '✓' : '—'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
