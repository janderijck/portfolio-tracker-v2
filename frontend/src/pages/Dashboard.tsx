import { usePortfolio } from '@/hooks/usePortfolio';
import { Link } from 'react-router-dom';
import { TrendingUp, TrendingDown, DollarSign, Euro, Loader2 } from 'lucide-react';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid
} from 'recharts';

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d'];

export default function Dashboard() {
  const { data, isLoading, error } = usePortfolio();

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
        Error loading portfolio: {error.message}
      </div>
    );
  }

  if (!data) return null;

  const { holdings, summary } = data;

  // Prepare chart data
  const pieData = holdings.map(h => ({
    name: h.ticker,
    value: h.current_value || h.total_invested_eur,
  }));

  const barData = holdings.map(h => ({
    name: h.ticker,
    gain_loss: h.gain_loss || 0,
  }));

  const formatCurrency = (value: number, currency: string = 'EUR') => {
    const symbol = currency === 'USD' ? '$' : '€';
    return `${symbol}${value.toLocaleString('nl-NL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const formatPercent = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  return (
    <div className="space-y-8">
      {/* Summary Cards */}
      {summary.has_usd_holdings && (
        <>
          {/* EUR Summary */}
          <div>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Euro className="h-5 w-5" /> EUR Portfolio
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <SummaryCard
                title="Geïnvesteerd"
                value={formatCurrency(summary.total_invested_eur)}
              />
              <SummaryCard
                title="Huidige Waarde"
                value={formatCurrency(summary.total_current_value_eur)}
              />
              <SummaryCard
                title="Dividend"
                value={formatCurrency(summary.total_dividends_eur)}
              />
              <SummaryCard
                title="W/V"
                value={formatCurrency(summary.total_gain_loss_eur)}
                trend={summary.total_gain_loss_eur >= 0 ? 'up' : 'down'}
              />
              <SummaryCard
                title="Rendement"
                value={formatPercent(summary.total_gain_loss_percent)}
                trend={summary.total_gain_loss_percent >= 0 ? 'up' : 'down'}
              />
            </div>
          </div>

          {/* USD Summary */}
          <div>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <DollarSign className="h-5 w-5" /> USD Portfolio
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <SummaryCard
                title="Geïnvesteerd"
                value={formatCurrency(summary.total_invested_usd || 0, 'USD')}
              />
              <SummaryCard
                title="Huidige Waarde"
                value={formatCurrency(summary.total_current_value_usd || 0, 'USD')}
              />
              <SummaryCard
                title="Dividend"
                value={formatCurrency(summary.total_dividends_usd || 0, 'USD')}
              />
              <SummaryCard
                title="W/V"
                value={formatCurrency(summary.total_gain_loss_usd || 0, 'USD')}
                trend={(summary.total_gain_loss_usd || 0) >= 0 ? 'up' : 'down'}
              />
              <SummaryCard
                title="Rendement"
                value={formatPercent(
                  summary.total_invested_usd
                    ? ((summary.total_gain_loss_usd || 0) / summary.total_invested_usd) * 100
                    : 0
                )}
                trend={(summary.total_gain_loss_usd || 0) >= 0 ? 'up' : 'down'}
              />
            </div>
          </div>
        </>
      )}

      {!summary.has_usd_holdings && (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <SummaryCard
            title="Totaal Geïnvesteerd"
            value={formatCurrency(summary.total_invested_eur)}
          />
          <SummaryCard
            title="Huidige Waarde"
            value={formatCurrency(summary.total_current_value_eur)}
          />
          <SummaryCard
            title="Totaal Dividend"
            value={formatCurrency(summary.total_dividends_eur)}
          />
          <SummaryCard
            title="W/V (excl. div)"
            value={formatCurrency(summary.total_gain_loss_eur)}
            trend={summary.total_gain_loss_eur >= 0 ? 'up' : 'down'}
          />
          <SummaryCard
            title="Rendement"
            value={formatPercent(summary.total_gain_loss_percent)}
            trend={summary.total_gain_loss_percent >= 0 ? 'up' : 'down'}
          />
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Allocation Pie Chart */}
        <div className="bg-card rounded-lg border p-6">
          <h3 className="text-lg font-semibold mb-4">Portfolio Allocatie</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {pieData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: number) => formatCurrency(value)} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Gain/Loss Bar Chart */}
        <div className="bg-card rounded-lg border p-6">
          <h3 className="text-lg font-semibold mb-4">Winst/Verlies per Aandeel</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip formatter={(value: number) => formatCurrency(value)} />
                <Bar
                  dataKey="gain_loss"
                  fill="#8884d8"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Holdings Table */}
      <div className="bg-card rounded-lg border">
        <div className="p-6 border-b">
          <h3 className="text-lg font-semibold">Holdings</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="text-left p-4 font-medium">Aandeel</th>
                <th className="text-right p-4 font-medium">Aantal</th>
                <th className="text-right p-4 font-medium">Aankoop</th>
                <th className="text-right p-4 font-medium">Huidig</th>
                <th className="text-right p-4 font-medium">Geïnvesteerd</th>
                <th className="text-right p-4 font-medium">W/V</th>
                <th className="text-right p-4 font-medium">%</th>
                <th className="text-left p-4 font-medium">Broker</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((holding) => {
                const symbol = holding.is_usd_account ? '$' : '€';
                return (
                  <tr key={holding.ticker} className="border-b hover:bg-muted/50">
                    <td className="p-4">
                      <Link
                        to={`/stock/${holding.ticker}`}
                        className="text-primary hover:underline font-medium"
                      >
                        {holding.name}
                      </Link>
                      <div className="text-sm text-muted-foreground">{holding.ticker}</div>
                    </td>
                    <td className="text-right p-4">{holding.quantity}</td>
                    <td className="text-right p-4">
                      {symbol}{holding.avg_purchase_price.toFixed(2)}
                    </td>
                    <td className="text-right p-4">
                      {holding.current_price
                        ? `${symbol}${holding.current_price.toFixed(2)}`
                        : 'N/A'}
                    </td>
                    <td className="text-right p-4">
                      {symbol}{(holding.is_usd_account ? holding.total_invested : holding.total_invested_eur).toFixed(2)}
                    </td>
                    <td className={`text-right p-4 font-medium ${
                      (holding.gain_loss || 0) >= 0 ? 'text-green-500' : 'text-red-500'
                    }`}>
                      {holding.gain_loss !== null
                        ? `${symbol}${holding.gain_loss >= 0 ? '+' : ''}${holding.gain_loss.toFixed(2)}`
                        : 'N/A'}
                    </td>
                    <td className={`text-right p-4 font-medium ${
                      (holding.gain_loss_percent || 0) >= 0 ? 'text-green-500' : 'text-red-500'
                    }`}>
                      {holding.gain_loss_percent !== null
                        ? formatPercent(holding.gain_loss_percent)
                        : 'N/A'}
                    </td>
                    <td className="p-4">{holding.broker}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function SummaryCard({
  title,
  value,
  trend,
}: {
  title: string;
  value: string;
  trend?: 'up' | 'down';
}) {
  return (
    <div className="bg-card rounded-lg border p-4">
      <div className="text-sm text-muted-foreground">{title}</div>
      <div className="flex items-center gap-2 mt-1">
        <span className={`text-xl font-bold ${
          trend === 'up' ? 'text-green-500' : trend === 'down' ? 'text-red-500' : ''
        }`}>
          {value}
        </span>
        {trend === 'up' && <TrendingUp className="h-4 w-4 text-green-500" />}
        {trend === 'down' && <TrendingDown className="h-4 w-4 text-red-500" />}
      </div>
    </div>
  );
}
