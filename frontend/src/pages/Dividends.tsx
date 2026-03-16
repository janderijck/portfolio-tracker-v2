import { useDividends, useDividendCalendar } from '@/hooks/usePortfolio';
import { formatCurrency, formatDate, frequencyLabel } from '@/utils/formatting';
import { Loader2 } from 'lucide-react';
import * as Tabs from '@radix-ui/react-tabs';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine,
} from 'recharts';

export default function Dividends() {
  const { data: dividends, isLoading, error } = useDividends();
  const { data: calendar, isLoading: calendarLoading } = useDividendCalendar();

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

  // Calendar data
  const currentMonth = new Date().toISOString().substring(0, 7);
  const calendarSummary = calendar?.monthly_summary ?? [];
  const totalReceived = calendarSummary.reduce((s, m) => s + m.received, 0);
  const totalForecasted = calendarSummary.reduce((s, m) => s + m.forecasted, 0);
  const monthCount = calendarSummary.length || 1;
  const avgPerMonth = (totalReceived + totalForecasted) / monthCount;

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Dividenden</h1>

      <Tabs.Root defaultValue="overzicht">
        <Tabs.List className="flex border-b mb-6">
          <Tabs.Trigger
            value="overzicht"
            className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground data-[state=active]:text-foreground data-[state=active]:border-b-2 data-[state=active]:border-primary -mb-px"
          >
            Overzicht
          </Tabs.Trigger>
          <Tabs.Trigger
            value="kalender"
            className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground data-[state=active]:text-foreground data-[state=active]:border-b-2 data-[state=active]:border-primary -mb-px"
          >
            Kalender
          </Tabs.Trigger>
        </Tabs.List>

        {/* ============================================================= */}
        {/* Overzicht Tab (existing content)                               */}
        {/* ============================================================= */}
        <Tabs.Content value="overzicht" className="space-y-8">
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
                    <th className="text-left p-4 font-medium">Aandeel</th>
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
                      <td className="p-4">
                        <div className="font-medium">{div.stock_name || div.ticker}</div>
                        {div.stock_name && <div className="text-sm text-muted-foreground">{div.ticker}</div>}
                      </td>
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
        </Tabs.Content>

        {/* ============================================================= */}
        {/* Kalender Tab (new)                                             */}
        {/* ============================================================= */}
        <Tabs.Content value="kalender" className="space-y-8">
          {calendarLoading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : calendar ? (
            <>
              {/* Calendar Summary Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-card rounded-lg border p-4">
                  <div className="text-sm text-muted-foreground">Ontvangen (12 mnd)</div>
                  <div className="text-xl font-bold mt-1 text-green-500">
                    {formatCurrency(totalReceived)}
                  </div>
                </div>
                <div className="bg-card rounded-lg border p-4">
                  <div className="text-sm text-muted-foreground">Verwacht (12 mnd)</div>
                  <div className="text-xl font-bold mt-1 text-blue-500">
                    {formatCurrency(totalForecasted)}
                  </div>
                </div>
                <div className="bg-card rounded-lg border p-4">
                  <div className="text-sm text-muted-foreground">Gemiddeld per Maand</div>
                  <div className="text-xl font-bold mt-1">
                    {formatCurrency(avgPerMonth)}
                  </div>
                </div>
              </div>

              {/* Combined BarChart */}
              {calendarSummary.length > 0 && (
                <div className="bg-card rounded-lg border p-6">
                  <h3 className="text-lg font-semibold mb-4">Historisch &amp; Verwacht Dividend</h3>
                  <div className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={calendarSummary}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="month" />
                        <YAxis />
                        <Tooltip formatter={(value: number) => formatCurrency(value)} />
                        <Legend />
                        <ReferenceLine
                          x={currentMonth}
                          stroke="#666"
                          strokeDasharray="3 3"
                          label={{ value: 'Vandaag', position: 'top', fontSize: 12 }}
                        />
                        <Bar dataKey="received" name="Ontvangen" fill="#22c55e" />
                        <Bar dataKey="forecasted" name="Verwacht" fill="#3b82f6" fillOpacity={0.6} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* Forecasted Dividends List */}
              {calendar.forecasted.length > 0 && (
                <div className="bg-card rounded-lg border">
                  <div className="p-6 border-b">
                    <h3 className="text-lg font-semibold">Verwachte Dividenden</h3>
                  </div>
                  <div className="divide-y">
                    {calendar.forecasted
                      .sort((a, b) => a.ex_date.localeCompare(b.ex_date))
                      .map((item, idx) => (
                        <div
                          key={`${item.ticker}-${item.ex_date}-${idx}`}
                          className="flex items-center justify-between p-4 border-dashed border-l-4 border-l-blue-400"
                        >
                          <div className="flex items-center gap-3">
                            <div>
                              <div className="font-medium">{item.stock_name || item.ticker}</div>
                              {item.stock_name && <div className="text-xs text-muted-foreground">{item.ticker}</div>}
                              <div className="text-sm text-muted-foreground">
                                {formatDate(item.ex_date)} · {frequencyLabel(item.frequency)}
                              </div>
                            </div>

                            <span className="text-xs bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 px-2 py-0.5 rounded-full">
                              Geschat
                            </span>
                          </div>
                          <div className="text-right font-medium text-blue-600 dark:text-blue-400">
                            {formatCurrency(item.estimated_amount, item.currency)}
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              )}

              {calendar.forecasted.length === 0 && (
                <div className="bg-card rounded-lg border p-8 text-center text-muted-foreground">
                  Geen verwachte dividenden gevonden. Zorg dat je aandelen met <code>pays_dividend</code> hebt ingesteld.
                </div>
              )}
            </>
          ) : (
            <div className="text-center text-muted-foreground">
              Kon kalenderdata niet laden.
            </div>
          )}
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}
