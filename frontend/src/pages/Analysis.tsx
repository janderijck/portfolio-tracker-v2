import { useCashFlow, useFXAnalysis, useCosts } from '@/hooks/usePortfolio';
import { Loader2 } from 'lucide-react';
import { useState } from 'react';

export default function Analysis() {
  const [selectedBroker, setSelectedBroker] = useState<string | undefined>();
  const { data: cashFlow, isLoading: loadingCash } = useCashFlow(selectedBroker);
  const { data: fxAnalysis, isLoading: loadingFX } = useFXAnalysis(selectedBroker);
  const { data: costs, isLoading: loadingCosts } = useCosts();

  const formatCurrency = (value: number, currency: string = 'EUR') => {
    const symbol = currency === 'USD' ? '$' : '€';
    return `${symbol}${value.toLocaleString('nl-NL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  if (loadingCash || loadingFX || loadingCosts) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Analyse</h1>
        <select
          value={selectedBroker || ''}
          onChange={(e) => setSelectedBroker(e.target.value || undefined)}
          className="px-3 py-2 rounded-md border bg-background"
        >
          <option value="">Alle Brokers</option>
          <option value="IBKR">IBKR</option>
          <option value="DeGiro">DeGiro</option>
        </select>
      </div>

      {/* Cash Flow */}
      {cashFlow && (
        <div className="bg-card rounded-lg border">
          <div className="p-6 border-b">
            <h3 className="text-lg font-semibold">Cash Flow</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-6">
            <div>
              <div className="text-sm text-muted-foreground">Deposits</div>
              <div className="text-xl font-bold mt-1">{formatCurrency(cashFlow.total_deposits)}</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Withdrawals</div>
              <div className="text-xl font-bold mt-1">{formatCurrency(cashFlow.total_withdrawals)}</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Portfolio Waarde</div>
              <div className="text-xl font-bold mt-1">{formatCurrency(cashFlow.current_portfolio_value)}</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Netto Cash Flow</div>
              <div className={`text-xl font-bold mt-1 ${cashFlow.net_cash_flow >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                {formatCurrency(cashFlow.net_cash_flow)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* FX Analysis */}
      {fxAnalysis && (
        <div className="bg-card rounded-lg border">
          <div className="p-6 border-b">
            <h3 className="text-lg font-semibold">FX Analyse (USD/EUR)</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-6">
            <div>
              <div className="text-sm text-muted-foreground">Gemiddelde Aankoopkoers</div>
              <div className="text-xl font-bold mt-1">{fxAnalysis.avg_purchase_rate.toFixed(4)}</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Huidige Koers</div>
              <div className="text-xl font-bold mt-1">{fxAnalysis.current_rate.toFixed(4)}</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">FX W/V</div>
              <div className={`text-xl font-bold mt-1 ${fxAnalysis.fx_gain_loss >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                {formatCurrency(fxAnalysis.fx_gain_loss)}
              </div>
            </div>
          </div>
          <div className="px-6 pb-6">
            <div className="text-sm text-muted-foreground">
              Totaal USD Invested: {formatCurrency(fxAnalysis.total_usd_invested, 'USD')} |
              Totaal EUR Equivalent: {formatCurrency(fxAnalysis.total_eur_equivalent)}
            </div>
          </div>
        </div>
      )}

      {/* Costs */}
      {costs && (
        <div className="bg-card rounded-lg border">
          <div className="p-6 border-b">
            <h3 className="text-lg font-semibold">Kosten Overzicht</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-6">
            <div>
              <div className="text-sm text-muted-foreground">Totale Kosten</div>
              <div className="text-xl font-bold mt-1">{formatCurrency(costs.total_fees)}</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Kosten per Transactie</div>
              <div className="text-xl font-bold mt-1">{formatCurrency(costs.avg_fee_per_transaction)}</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Aantal Transacties</div>
              <div className="text-xl font-bold mt-1">{costs.transaction_count}</div>
            </div>
          </div>

          {/* Costs by Broker */}
          <div className="px-6 pb-6">
            <h4 className="text-md font-semibold mb-4">Kosten per Broker</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.entries(costs.by_broker).map(([broker, brokerCosts]) => (
                <div key={broker} className="bg-muted/50 rounded-lg p-4">
                  <div className="font-medium">{broker}</div>
                  <div className="text-sm text-muted-foreground mt-1">
                    {formatCurrency(brokerCosts.total)} ({brokerCosts.count} transacties)
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
