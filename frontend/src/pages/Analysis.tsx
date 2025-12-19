import { usePerformance, useDividendSummary, useCosts, useAllocation } from '@/hooks/usePortfolio';
import { Loader2, TrendingUp, TrendingDown, PiggyBank, Receipt, PieChart } from 'lucide-react';

export default function Analysis() {
  const { data: performance, isLoading: loadingPerformance } = usePerformance();
  const { data: dividends, isLoading: loadingDividends } = useDividendSummary();
  const { data: costs, isLoading: loadingCosts } = useCosts();
  const { data: allocation, isLoading: loadingAllocation } = useAllocation();

  const formatCurrency = (value: number, currency: string = 'EUR') => {
    const symbol = currency === 'USD' ? '$' : '€';
    return `${symbol}${value.toLocaleString('nl-NL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const formatPercent = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const isLoading = loadingPerformance || loadingDividends || loadingCosts || loadingAllocation;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Analyse</h1>

      {/* Performance Overview */}
      {performance && (
        <div className="bg-card rounded-lg border">
          <div className="p-6 border-b flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            <h3 className="text-lg font-semibold">Portfolio Prestaties</h3>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
              <div>
                <div className="text-sm text-muted-foreground">Totaal Geïnvesteerd</div>
                <div className="text-2xl font-bold mt-1">{formatCurrency(performance.total_invested)}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Huidige Waarde</div>
                <div className="text-2xl font-bold mt-1">{formatCurrency(performance.current_value)}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Koerswinst/-verlies</div>
                <div className={`text-2xl font-bold mt-1 ${performance.total_gain_loss >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                  {formatCurrency(performance.total_gain_loss)}
                  <span className="text-sm ml-1">({formatPercent(performance.total_gain_loss_percent)})</span>
                </div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Totaal Rendement (incl. dividend)</div>
                <div className={`text-2xl font-bold mt-1 ${performance.total_return >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                  {formatCurrency(performance.total_return)}
                  <span className="text-sm ml-1">({formatPercent(performance.total_return_percent)})</span>
                </div>
              </div>
            </div>

            {/* Best/Worst Performers */}
            {(performance.best_performer || performance.worst_performer) && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t">
                {performance.best_performer && (
                  <div className="flex items-center gap-3 bg-green-500/10 rounded-lg p-3">
                    <TrendingUp className="h-5 w-5 text-green-500" />
                    <div>
                      <div className="text-sm text-muted-foreground">Beste Presteerder</div>
                      <div className="font-semibold">{performance.best_performer}</div>
                      <div className="text-green-500 text-sm">{formatPercent(performance.best_performer_percent!)}</div>
                    </div>
                  </div>
                )}
                {performance.worst_performer && (
                  <div className="flex items-center gap-3 bg-red-500/10 rounded-lg p-3">
                    <TrendingDown className="h-5 w-5 text-red-500" />
                    <div>
                      <div className="text-sm text-muted-foreground">Slechtste Presteerder</div>
                      <div className="font-semibold">{performance.worst_performer}</div>
                      <div className="text-red-500 text-sm">{formatPercent(performance.worst_performer_percent!)}</div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Dividend Summary */}
      {dividends && (
        <div className="bg-card rounded-lg border">
          <div className="p-6 border-b flex items-center gap-2">
            <PiggyBank className="h-5 w-5" />
            <h3 className="text-lg font-semibold">Dividend Overzicht</h3>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
              <div>
                <div className="text-sm text-muted-foreground">Bruto Ontvangen</div>
                <div className="text-xl font-bold mt-1">{formatCurrency(dividends.total_received)}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Ingehouden Belasting</div>
                <div className="text-xl font-bold mt-1 text-red-500">-{formatCurrency(dividends.total_withheld_tax)}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Netto Ontvangen</div>
                <div className="text-xl font-bold mt-1 text-green-500">{formatCurrency(dividends.total_net)}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Dividend Yield</div>
                <div className="text-xl font-bold mt-1">{dividends.dividend_yield.toFixed(2)}%</div>
              </div>
            </div>

            {/* By Year */}
            {Object.keys(dividends.by_year).length > 0 && (
              <div className="pt-4 border-t">
                <h4 className="text-md font-semibold mb-3">Per Jaar</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {Object.entries(dividends.by_year)
                    .sort(([a], [b]) => b.localeCompare(a))
                    .map(([year, total]) => (
                      <div key={year} className="bg-muted/50 rounded-lg p-3">
                        <div className="text-sm text-muted-foreground">{year}</div>
                        <div className="font-semibold">{formatCurrency(total)}</div>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* By Ticker */}
            {Object.keys(dividends.by_ticker).length > 0 && (
              <div className="pt-4 border-t mt-4">
                <h4 className="text-md font-semibold mb-3">Per Aandeel</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {Object.entries(dividends.by_ticker)
                    .sort(([, a], [, b]) => b.total - a.total)
                    .map(([ticker, data]) => (
                      <div key={ticker} className="bg-muted/50 rounded-lg p-3">
                        <div className="font-medium">{ticker}</div>
                        <div className="text-sm">{formatCurrency(data.total)}</div>
                        <div className="text-xs text-muted-foreground">{data.count}x</div>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Costs Summary */}
      {costs && (
        <div className="bg-card rounded-lg border">
          <div className="p-6 border-b flex items-center gap-2">
            <Receipt className="h-5 w-5" />
            <h3 className="text-lg font-semibold">Kosten Overzicht</h3>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
              <div>
                <div className="text-sm text-muted-foreground">Totale Kosten</div>
                <div className="text-xl font-bold mt-1">{formatCurrency(costs.total_fees)}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Totale Belastingen</div>
                <div className="text-xl font-bold mt-1">{formatCurrency(costs.total_taxes)}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Gemiddeld per Transactie</div>
                <div className="text-xl font-bold mt-1">{formatCurrency(costs.avg_fee_per_transaction)}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Kosten % van Invested</div>
                <div className="text-xl font-bold mt-1">{costs.fees_as_percent_of_invested.toFixed(2)}%</div>
              </div>
            </div>

            {/* By Broker */}
            {Object.keys(costs.by_broker).length > 0 && (
              <div className="pt-4 border-t">
                <h4 className="text-md font-semibold mb-3">Per Broker</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.entries(costs.by_broker).map(([broker, data]) => (
                    <div key={broker} className="bg-muted/50 rounded-lg p-4">
                      <div className="font-medium">{broker}</div>
                      <div className="text-sm mt-1">
                        {formatCurrency(data.total)} ({data.count} transacties)
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Allocation Summary */}
      {allocation && (
        <div className="bg-card rounded-lg border">
          <div className="p-6 border-b flex items-center gap-2">
            <PieChart className="h-5 w-5" />
            <h3 className="text-lg font-semibold">Portfolio Allocatie</h3>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* By Broker */}
              {allocation.by_broker.length > 0 && (
                <div>
                  <h4 className="text-md font-semibold mb-3">Per Broker</h4>
                  <div className="space-y-2">
                    {allocation.by_broker.map((item) => (
                      <div key={item.name} className="flex justify-between items-center">
                        <span>{item.name}</span>
                        <div className="text-right">
                          <div className="font-semibold">{item.percentage.toFixed(1)}%</div>
                          <div className="text-xs text-muted-foreground">{formatCurrency(item.value)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* By Country */}
              {allocation.by_country.length > 0 && (
                <div>
                  <h4 className="text-md font-semibold mb-3">Per Land</h4>
                  <div className="space-y-2">
                    {allocation.by_country.map((item) => (
                      <div key={item.name} className="flex justify-between items-center">
                        <span>{item.name}</span>
                        <div className="text-right">
                          <div className="font-semibold">{item.percentage.toFixed(1)}%</div>
                          <div className="text-xs text-muted-foreground">{formatCurrency(item.value)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* By Asset Type */}
              {allocation.by_asset_type.length > 0 && (
                <div>
                  <h4 className="text-md font-semibold mb-3">Per Type</h4>
                  <div className="space-y-2">
                    {allocation.by_asset_type.map((item) => (
                      <div key={item.name} className="flex justify-between items-center">
                        <span>{item.name === 'STOCK' ? 'Aandelen' : item.name === 'REIT' ? 'REITs' : item.name}</span>
                        <div className="text-right">
                          <div className="font-semibold">{item.percentage.toFixed(1)}%</div>
                          <div className="text-xs text-muted-foreground">{formatCurrency(item.value)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
