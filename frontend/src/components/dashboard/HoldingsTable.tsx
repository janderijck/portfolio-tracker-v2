import { Link } from 'react-router-dom';
import { DollarSign, RefreshCw, Hand, Zap, ArrowUpDown, ChevronUp, ChevronDown } from 'lucide-react';
import type { PortfolioHolding } from '@/types';
import { formatPercent, getCurrencySymbol, getManualPriceAgeColor } from '@/utils/formatting';

export type SortField = 'name' | 'quantity' | 'avg_purchase_price' | 'current_price' | 'current_value_eur' | 'total_invested_eur' | 'gain_loss' | 'gain_loss_percent' | 'change_percent' | 'sentiment_bullish_pct' | 'broker';
export type SortDir = 'asc' | 'desc';

function SortHeader({ field, label, sortField, sortDir, onToggle, align = 'right' }: {
  field: SortField; label: string | React.ReactNode; sortField: SortField; sortDir: SortDir;
  onToggle: (f: SortField) => void; align?: 'left' | 'right' | 'center';
}) {
  const active = sortField === field;
  return (
    <th
      className={`p-4 font-medium cursor-pointer select-none hover:bg-muted/80 transition-colors ${align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left'}`}
      onClick={() => onToggle(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {active ? (sortDir === 'asc' ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />) : <ArrowUpDown className="h-3 w-3 text-muted-foreground/50" />}
      </span>
    </th>
  );
}

interface HoldingsTableProps {
  title: string;
  holdings: PortfolioHolding[];
  isUsd: boolean;
  sortField: SortField;
  sortDir: SortDir;
  onToggleSort: (field: SortField) => void;
  isRefetching: boolean;
  onRefetch: () => void;
}

export default function HoldingsTable({
  title,
  holdings,
  isUsd,
  sortField,
  sortDir,
  onToggleSort,
  isRefetching,
  onRefetch,
}: HoldingsTableProps) {
  const symbol = getCurrencySymbol(isUsd ? 'USD' : 'EUR');
  const eurSymbol = getCurrencySymbol('EUR');

  return (
    <div className="bg-card rounded-lg border">
      <div className="p-6 border-b flex justify-between items-center">
        <h3 className="text-lg font-semibold">{title}</h3>
        <button
          onClick={onRefetch}
          disabled={isRefetching}
          className="flex items-center gap-2 px-3 py-1.5 text-sm border rounded-md hover:bg-accent transition-colors disabled:opacity-50"
          title="Ververs portfolio data"
        >
          <RefreshCw className={`h-4 w-4 ${isRefetching ? 'animate-spin' : ''}`} />
          Verversen
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-muted/50">
              <SortHeader field="name" label="Aandeel" sortField={sortField} sortDir={sortDir} onToggle={onToggleSort} align="left" />
              <th className="text-center p-4 font-medium" title="Dividend">
                <DollarSign className="h-4 w-4 inline" />
              </th>
              <SortHeader field="quantity" label="Aantal" sortField={sortField} sortDir={sortDir} onToggle={onToggleSort} />
              <SortHeader field="avg_purchase_price" label="Aankoop" sortField={sortField} sortDir={sortDir} onToggle={onToggleSort} />
              <SortHeader field="current_price" label="Huidig" sortField={sortField} sortDir={sortDir} onToggle={onToggleSort} />
              <SortHeader field="current_value_eur" label={isUsd ? 'Waarde (EUR)' : 'Waarde'} sortField={sortField} sortDir={sortDir} onToggle={onToggleSort} />
              <SortHeader field="total_invested_eur" label="Ge&#239;nvesteerd" sortField={sortField} sortDir={sortDir} onToggle={onToggleSort} />
              <SortHeader field="gain_loss" label="W/V" sortField={sortField} sortDir={sortDir} onToggle={onToggleSort} />
              <SortHeader field="gain_loss_percent" label="%" sortField={sortField} sortDir={sortDir} onToggle={onToggleSort} />
              <SortHeader field="change_percent" label="Dag" sortField={sortField} sortDir={sortDir} onToggle={onToggleSort} />
              <SortHeader field="sentiment_bullish_pct" label="Sentiment" sortField={sortField} sortDir={sortDir} onToggle={onToggleSort} />
              <SortHeader field="broker" label="Broker" sortField={sortField} sortDir={sortDir} onToggle={onToggleSort} align="left" />
            </tr>
          </thead>
          <tbody>
            {holdings.map((holding) => (
              <tr key={`${holding.ticker}-${holding.broker}`} className="border-b hover:bg-muted/50">
                <td className="p-4">
                  <Link
                    to={`/stock/${holding.ticker}`}
                    className="text-primary hover:underline font-medium"
                  >
                    {holding.name}
                  </Link>
                  <div className="text-sm text-muted-foreground">{holding.ticker}</div>
                </td>
                <td className="text-center p-4">
                  {holding.pays_dividend && (
                    <span title="Keert dividend uit"><DollarSign className="h-4 w-4 inline text-green-500" /></span>
                  )}
                </td>
                <td className="text-right p-4">{holding.quantity}</td>
                <td className="text-right p-4">
                  {symbol}{holding.avg_purchase_price.toFixed(2)}
                </td>
                <td className={`text-right p-4 ${getManualPriceAgeColor(holding.manual_price_date)}`}>
                  <div className="flex items-center justify-end gap-2">
                    <span>
                      {holding.current_price
                        ? `${symbol}${holding.current_price.toFixed(2)}`
                        : 'N/A'}
                    </span>
                    {holding.manual_price_date ? (
                      <span title="Handmatige koers"><Hand className="h-3.5 w-3.5 text-muted-foreground" /></span>
                    ) : (
                      <span title="Automatische koers"><Zap className="h-3.5 w-3.5 text-muted-foreground" /></span>
                    )}
                  </div>
                </td>
                <td className="text-right p-4">
                  {holding.current_value_eur !== null
                    ? `${isUsd ? eurSymbol : symbol}${holding.current_value_eur.toFixed(2)}`
                    : 'N/A'}
                </td>
                <td className="text-right p-4">
                  {isUsd
                    ? `${symbol}${holding.total_invested.toFixed(2)}`
                    : `${symbol}${holding.total_invested_eur.toFixed(2)}`
                  }
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
                <td className={`text-right p-4 text-sm ${
                  (holding.change_percent ?? 0) >= 0 ? 'text-green-500' : 'text-red-500'
                }`}>
                  {holding.change_percent !== null && holding.change_percent !== undefined
                    ? `${holding.change_percent >= 0 ? '+' : ''}${holding.change_percent.toFixed(2)}%`
                    : ''}
                </td>
                <td className="text-right p-4 text-sm">
                  {holding.sentiment_bullish_pct !== null && holding.sentiment_bullish_pct !== undefined ? (
                    <div className="flex items-center justify-end gap-1.5">
                      <div className="w-12 h-2 rounded-full bg-red-500/20 overflow-hidden">
                        <div
                          className="h-full bg-green-500 rounded-full"
                          style={{ width: `${holding.sentiment_bullish_pct}%` }}
                        />
                      </div>
                      <span className={holding.sentiment_bullish_pct >= 50 ? 'text-green-500' : 'text-red-500'}>
                        {holding.sentiment_bullish_pct.toFixed(0)}%
                      </span>
                    </div>
                  ) : (
                    <span className="text-muted-foreground/30">—</span>
                  )}
                </td>
                <td className="p-4">{holding.broker}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
