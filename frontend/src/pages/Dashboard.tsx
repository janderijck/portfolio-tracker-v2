import { useState, useMemo } from 'react';
import { usePortfolio, useMovers, useBrokers, useCashSummary, useBrokerDetails } from '@/hooks/usePortfolio';
import { Link, useSearchParams } from 'react-router-dom';
import { TrendingUp, TrendingDown, Loader2, Plus, RefreshCw, Wallet } from 'lucide-react';
import {
  AreaChart, Area, ResponsiveContainer, Tooltip,
  XAxis, YAxis, CartesianGrid
} from 'recharts';
import type { PortfolioHolding } from '@/types';
import { refreshPrices, getPortfolioEvolution } from '@/api/client';
import { formatCurrency, formatPercent, getCurrencySymbol } from '@/utils/formatting';
import AddStockModal from '@/components/dashboard/AddStockModal';
import HoldingsTable, { type SortField, type SortDir } from '@/components/dashboard/HoldingsTable';

import { useQuery, useQueryClient } from '@tanstack/react-query';

export default function Dashboard() {
  const { data, isLoading, error, refetch, isRefetching } = usePortfolio();
  const { data: brokers } = useBrokers();
  const { data: cashSummary } = useCashSummary();
  const { data: brokerDetails } = useBrokerDetails();
  const queryClient = useQueryClient();

  const [isRefreshingPrices, setIsRefreshingPrices] = useState(false);

  const handleRefreshPrices = async () => {
    setIsRefreshingPrices(true);
    try {
      await refreshPrices();
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
    } catch {
      // silently fail
    } finally {
      setIsRefreshingPrices(false);
    }
  };
  const [showAddStock, setShowAddStock] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedBroker = searchParams.get('broker') || 'all';
  const selectedAccountType = searchParams.get('account') || 'all';
  const setSelectedBroker = (broker: string) => {
    if (broker === 'all') {
      searchParams.delete('broker');
    } else {
      searchParams.set('broker', broker);
    }
    setSearchParams(searchParams, { replace: true });
  };
  const setSelectedAccountType = (accountType: string) => {
    if (accountType === 'all') {
      searchParams.delete('account');
    } else {
      searchParams.set('account', accountType);
    }
    // Reset broker selection when changing account type
    searchParams.delete('broker');
    setSearchParams(searchParams, { replace: true });
  };

  // Build account type map from broker details
  const accountTypeMap = useMemo(() => {
    const map: Record<string, string> = {};
    brokerDetails?.forEach(b => {
      map[b.broker_name] = b.account_type || 'Privé';
    });
    return map;
  }, [brokerDetails]);

  // Filter brokers by selected account type
  const filteredBrokerNames = useMemo(() =>
    selectedAccountType === 'all'
      ? (brokers ?? [])
      : (brokers ?? []).filter(b => accountTypeMap[b] === selectedAccountType),
    [brokers, selectedAccountType, accountTypeMap]);

  const { data: evolutionData = [] } = useQuery({
    queryKey: ['portfolio-evolution', selectedBroker],
    queryFn: () => getPortfolioEvolution(selectedBroker === 'all' ? undefined : selectedBroker),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Mover period state (must be before early returns)
  const [moverPeriod, setMoverPeriod] = useState<string>('1d');
  const { data: moversData, isLoading: isLoadingMovers } = useMovers(moverPeriod);

  // Sort state for EUR and USD tables (must be before early returns)
  const [eurSortField, setEurSortField] = useState<SortField>('gain_loss');
  const [eurSortDir, setEurSortDir] = useState<SortDir>('desc');
  const [usdSortField, setUsdSortField] = useState<SortField>('gain_loss');
  const [usdSortDir, setUsdSortDir] = useState<SortDir>('desc');


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

  // Filter holdings by account type and broker
  const accountFilteredHoldings = selectedAccountType === 'all'
    ? holdings
    : holdings.filter(h => accountTypeMap[h.broker] === selectedAccountType);
  const filteredHoldings = selectedBroker === 'all'
    ? accountFilteredHoldings
    : accountFilteredHoldings.filter(h => h.broker === selectedBroker);

  // Recalculate summary for filtered holdings
  const isAllUnfiltered = selectedBroker === 'all' && selectedAccountType === 'all';
  const filteredSummary = useMemo(() => {
    if (isAllUnfiltered) return summary;
    const total_invested_eur = filteredHoldings.reduce((sum, h) => sum + h.total_invested_eur, 0);
    const total_current_value_eur = filteredHoldings.reduce((sum, h) => sum + (h.current_value_eur ?? 0), 0);
    const total_gain_loss_eur = filteredHoldings.reduce((sum, h) => sum + (h.gain_loss ?? 0), 0);
    const total_gain_loss_percent = total_invested_eur > 0
      ? (total_gain_loss_eur / total_invested_eur) * 100
      : 0;
    return { total_invested_eur, total_current_value_eur, total_gain_loss_eur, total_gain_loss_percent };
  }, [isAllUnfiltered, summary, filteredHoldings]);

  // Filter cash by account type and broker
  const accountFilteredCashItems = selectedAccountType === 'all'
    ? (cashSummary?.per_broker ?? [])
    : (cashSummary?.per_broker.filter(b => accountTypeMap[b.broker_name] === selectedAccountType) ?? []);
  const filteredCashItems = selectedBroker === 'all'
    ? accountFilteredCashItems
    : accountFilteredCashItems.filter(b => b.broker_name === selectedBroker);
  const filteredCashEur = isAllUnfiltered
    ? (cashSummary?.total_cash_eur ?? 0)
    : filteredCashItems.reduce((sum, b) => sum + b.cash_balance_eur, 0);
  const cashEurOnly = filteredCashItems.filter(b => b.cash_currency === 'EUR').reduce((sum, b) => sum + b.cash_balance, 0);
  const cashUsd = filteredCashItems.filter(b => b.cash_currency === 'USD').reduce((sum, b) => sum + b.cash_balance, 0);


  // Split holdings into EUR and USD
  const eurHoldings = filteredHoldings.filter(h => !h.is_usd_account);
  const usdHoldings = filteredHoldings.filter(h => h.is_usd_account);

  // Sort helpers
  const sortHoldings = (items: PortfolioHolding[], field: SortField, dir: SortDir) => {
    return [...items].sort((a, b) => {
      let av: number | string = 0;
      let bv: number | string = 0;
      if (field === 'name') { av = a.name.toLowerCase(); bv = b.name.toLowerCase(); }
      else if (field === 'broker') { av = a.broker.toLowerCase(); bv = b.broker.toLowerCase(); }
      else { av = (a as any)[field] ?? -Infinity; bv = (b as any)[field] ?? -Infinity; }
      if (av < bv) return dir === 'asc' ? -1 : 1;
      if (av > bv) return dir === 'asc' ? 1 : -1;
      return 0;
    });
  };
  const toggleEurSort = (field: SortField) => {
    if (eurSortField === field) { setEurSortDir(d => d === 'asc' ? 'desc' : 'asc'); }
    else { setEurSortField(field); setEurSortDir(field === 'name' || field === 'broker' ? 'asc' : 'desc'); }
  };
  const toggleUsdSort = (field: SortField) => {
    if (usdSortField === field) { setUsdSortDir(d => d === 'asc' ? 'desc' : 'asc'); }
    else { setUsdSortField(field); setUsdSortDir(field === 'name' || field === 'broker' ? 'asc' : 'desc'); }
  };
  const sortedEurHoldings = useMemo(
    () => sortHoldings(eurHoldings, eurSortField, eurSortDir),
    [eurHoldings, eurSortField, eurSortDir]
  );
  const sortedUsdHoldings = useMemo(
    () => sortHoldings(usdHoldings, usdSortField, usdSortDir),
    [usdHoldings, usdSortField, usdSortDir]
  );

  // Currency-split summaries
  const hasUsd = usdHoldings.length > 0;
  const hasEur = eurHoldings.length > 0;
  const eurSummary = useMemo(() => ({
    invested: eurHoldings.reduce((sum, h) => sum + h.total_invested_eur, 0),
    value: eurHoldings.reduce((sum, h) => sum + (h.current_value_eur ?? 0), 0),
  }), [eurHoldings]);
  const usdSummary = useMemo(() => ({
    invested: usdHoldings.reduce((sum, h) => sum + h.total_invested, 0),
    value: usdHoldings.reduce((sum, h) => sum + (h.current_value ?? 0), 0),
    invested_eur: usdHoldings.reduce((sum, h) => sum + h.total_invested_eur, 0),
    value_eur: usdHoldings.reduce((sum, h) => sum + (h.current_value_eur ?? 0), 0),
  }), [usdHoldings]);

  return (
    <div className="space-y-8">
      <AddStockModal open={showAddStock} onClose={() => setShowAddStock(false)} brokers={brokers} />

      {/* Action Buttons */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-3">
          <button
            onClick={handleRefreshPrices}
            disabled={isRefreshingPrices}
            className="flex items-center gap-2 px-4 py-2 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/90 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshingPrices ? 'animate-spin' : ''}`} />
            {isRefreshingPrices ? 'Bezig...' : 'Koersen Verversen'}
          </button>
          {data.prices_updated_at && (
            <span className="text-xs text-muted-foreground">
              Bijgewerkt: {new Date(data.prices_updated_at).toLocaleString('nl-BE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-md border overflow-hidden">
            {(['all', 'Privé', 'TechVibe'] as const).map((type) => (
              <button
                key={type}
                onClick={() => setSelectedAccountType(type)}
                className={`px-3 py-2 text-sm font-medium transition-colors ${
                  selectedAccountType === type
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-background hover:bg-accent'
                }`}
              >
                {type === 'all' ? 'Alles' : type}
              </button>
            ))}
          </div>
          <select
            value={selectedBroker}
            onChange={(e) => setSelectedBroker(e.target.value)}
            className="px-3 py-2 border rounded-md bg-background text-sm"
          >
            <option value="all">Alle Brokers</option>
            {filteredBrokerNames.map((broker) => (
              <option key={broker} value={broker}>{broker}</option>
            ))}
          </select>
        </div>
        <button
          onClick={() => setShowAddStock(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          Aandeel Toevoegen
        </button>
      </div>

      {/* Summary Cards */}
      {hasUsd && hasEur ? (
        <div className="space-y-3">
          {/* EUR row */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <SummaryCard
              title="Geïnvesteerd EUR"
              value={formatCurrency(eurSummary.invested)}
            />
            <SummaryCard
              title="Waarde EUR"
              value={formatCurrency(eurSummary.value)}
            />
            <SummaryCard
              title="W/V EUR"
              value={formatCurrency(eurSummary.value - eurSummary.invested)}
              trend={eurSummary.value - eurSummary.invested >= 0 ? 'up' : 'down'}
            />
            <SummaryCard
              title="Rendement EUR"
              value={formatPercent(eurSummary.invested > 0 ? ((eurSummary.value - eurSummary.invested) / eurSummary.invested) * 100 : 0)}
              trend={eurSummary.value - eurSummary.invested >= 0 ? 'up' : 'down'}
            />
          </div>
          {/* USD row */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <SummaryCard
              title="Geïnvesteerd USD"
              value={`$${usdSummary.invested.toFixed(2)}`}
              subtitle={`${formatCurrency(usdSummary.invested_eur)}`}
            />
            <SummaryCard
              title="Waarde USD"
              value={`$${usdSummary.value.toFixed(2)}`}
              subtitle={`${formatCurrency(usdSummary.value_eur)}`}
            />
            <SummaryCard
              title="W/V USD"
              value={`$${(usdSummary.value - usdSummary.invested).toFixed(2)}`}
              trend={usdSummary.value - usdSummary.invested >= 0 ? 'up' : 'down'}
              subtitle={`${formatCurrency(usdSummary.value_eur - usdSummary.invested_eur)}`}
            />
            <SummaryCard
              title="Rendement USD"
              value={formatPercent(usdSummary.invested > 0 ? ((usdSummary.value - usdSummary.invested) / usdSummary.invested) * 100 : 0)}
              trend={usdSummary.value - usdSummary.invested >= 0 ? 'up' : 'down'}
            />
          </div>
          {/* Totals row */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <SummaryCard
              title="Totaal Geïnvesteerd"
              value={formatCurrency(filteredSummary.total_invested_eur)}
            />
            <SummaryCard
              title="Totale Waarde"
              value={formatCurrency(filteredSummary.total_current_value_eur)}
            />
            <SummaryCard
              title="Cash"
              value={formatCurrency(filteredCashEur)}
              icon={<Wallet className="h-4 w-4 text-muted-foreground" />}
            />
            <SummaryCard
              title="W/V Totaal"
              value={formatCurrency(filteredSummary.total_gain_loss_eur)}
              trend={filteredSummary.total_gain_loss_eur >= 0 ? 'up' : 'down'}
            />
            <SummaryCard
              title="Rendement Totaal"
              value={formatPercent(filteredSummary.total_gain_loss_percent)}
              trend={filteredSummary.total_gain_loss_percent >= 0 ? 'up' : 'down'}
            />
          </div>
        </div>
      ) : hasUsd ? (
        <div className="space-y-3">
          {/* USD holdings + cash */}
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <SummaryCard
              title="Geïnvesteerd"
              value={`$${usdSummary.invested.toFixed(2)}`}
              subtitle={formatCurrency(usdSummary.invested_eur)}
            />
            <SummaryCard
              title="Huidige Waarde"
              value={`$${usdSummary.value.toFixed(2)}`}
              subtitle={formatCurrency(usdSummary.value_eur)}
            />
            <SummaryCard
              title="Cash"
              value={cashUsd > 0 && cashEurOnly > 0
                ? `$${cashUsd.toFixed(2)} + ${formatCurrency(cashEurOnly)}`
                : cashUsd > 0
                ? `$${cashUsd.toFixed(2)}`
                : formatCurrency(cashEurOnly)}
              icon={<Wallet className="h-4 w-4 text-muted-foreground" />}
              subtitle={cashUsd > 0 ? `Totaal: ${formatCurrency(filteredCashEur)}` : undefined}
            />
            <SummaryCard
              title="Totaal in EUR"
              value={formatCurrency(filteredSummary.total_current_value_eur + filteredCashEur)}
            />
            <SummaryCard
              title="W/V"
              value={`$${(usdSummary.value - usdSummary.invested).toFixed(2)}`}
              trend={usdSummary.value - usdSummary.invested >= 0 ? 'up' : 'down'}
              subtitle={formatCurrency(usdSummary.value_eur - usdSummary.invested_eur)}
            />
            <SummaryCard
              title="Rendement"
              value={formatPercent(usdSummary.invested > 0 ? ((usdSummary.value - usdSummary.invested) / usdSummary.invested) * 100 : 0)}
              trend={usdSummary.value - usdSummary.invested >= 0 ? 'up' : 'down'}
            />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <SummaryCard
            title="Totaal Geïnvesteerd"
            value={formatCurrency(filteredSummary.total_invested_eur)}
          />
          <SummaryCard
            title="Huidige Waarde"
            value={formatCurrency(filteredSummary.total_current_value_eur)}
          />
          <SummaryCard
            title="Cash"
            value={formatCurrency(filteredCashEur)}
            icon={<Wallet className="h-4 w-4 text-muted-foreground" />}
          />
          <SummaryCard
            title="Totale Waarde"
            value={formatCurrency(filteredSummary.total_current_value_eur + filteredCashEur)}
          />
          <SummaryCard
            title="W/V"
            value={formatCurrency(filteredSummary.total_gain_loss_eur)}
            trend={filteredSummary.total_gain_loss_eur >= 0 ? 'up' : 'down'}
          />
          <SummaryCard
            title="Rendement"
            value={formatPercent(filteredSummary.total_gain_loss_percent)}
            trend={filteredSummary.total_gain_loss_percent >= 0 ? 'up' : 'down'}
          />
        </div>
      )}

      {/* Per-broker cash breakdown */}
      {filteredCashItems.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {filteredCashItems.map((item) => (
            <span
              key={`${item.broker_name}-${item.cash_currency}`}
              className="inline-flex items-center gap-1.5 px-3 py-1 bg-card border border-border rounded-md text-sm"
            >
              <Wallet className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="font-medium">{item.broker_name}</span>
              <span className="text-muted-foreground">
                {item.cash_currency === 'EUR'
                  ? formatCurrency(item.cash_balance)
                  : `${getCurrencySymbol(item.cash_currency)}${item.cash_balance.toFixed(2)} (${formatCurrency(item.cash_balance_eur)})`
                }
              </span>
            </span>
          ))}
        </div>
      )}

      {/* Portfolio Evolution Chart */}
      {evolutionData.length > 0 && (() => {
        const latestGain = evolutionData[evolutionData.length - 1]?.gain ?? 0;
        const color = latestGain >= 0 ? '#22c55e' : '#ef4444';
        return (
          <div className="bg-card rounded-lg border p-6">
            <h3 className="text-lg font-semibold mb-4">Winst/Verlies Evolutie</h3>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={evolutionData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(value) => {
                      const [y, m] = value.split('-');
                      const months = ['jan', 'feb', 'mrt', 'apr', 'mei', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec'];
                      return `${months[parseInt(m, 10) - 1]} '${y.slice(2)}`;
                    }}
                  />
                  <YAxis
                    tickFormatter={(value) => formatCurrency(value)}
                  />
                  <Tooltip
                    formatter={(value: number, name: string) => {
                      const label = name === 'gain' ? 'W/V' : name === 'invested' ? 'Geïnvesteerd' : 'Waarde';
                      return [formatCurrency(value), label];
                    }}
                    labelFormatter={(label) => {
                      const [y, m] = label.split('-');
                      const months = ['januari', 'februari', 'maart', 'april', 'mei', 'juni', 'juli', 'augustus', 'september', 'oktober', 'november', 'december'];
                      return `${months[parseInt(m, 10) - 1]} ${y}`;
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="gain"
                    stroke={color}
                    fill={color}
                    fillOpacity={0.15}
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        );
      })()}

      {/* Top Movers */}
      {filteredHoldings.length > 0 && (() => {
        const periodLabels: Record<string, string> = { '1d': 'dag', '1w': 'week', '1m': 'maand', 'ytd': 'YTD', '1y': 'jaar' };
        const periodLabel = periodLabels[moverPeriod] || moverPeriod;

        // Build movers list based on selected period
        let moverItems: { ticker: string; name: string; change_percent: number; broker?: string }[] = [];
        if (moverPeriod === '1d') {
          moverItems = filteredHoldings
            .filter(h => h.change_percent !== null && h.change_percent !== undefined)
            .map(h => ({ ticker: h.ticker, name: h.name, change_percent: h.change_percent!, broker: h.broker }));
        } else if (moversData) {
          // Filter movers by broker selection (match tickers in filtered holdings)
          const filteredTickers = new Set(filteredHoldings.map(h => h.ticker));
          // Deduplicate by ticker (holdings can have same ticker across brokers)
          const seen = new Set<string>();
          moverItems = moversData
            .filter(m => filteredTickers.has(m.ticker))
            .filter(m => { if (seen.has(m.ticker)) return false; seen.add(m.ticker); return true; })
            .map(m => ({ ticker: m.ticker, name: m.name, change_percent: m.change_percent }));
        }

        const sorted = [...moverItems].sort((a, b) => b.change_percent - a.change_percent);
        const topGainers = sorted.filter(h => h.change_percent > 0);
        const topLosers = sorted.filter(h => h.change_percent < 0).reverse();

        const periodButtons = (
          <div className="flex gap-1">
            {(['1d', '1w', '1m', 'ytd', '1y'] as const).map(p => (
              <button
                key={p}
                onClick={() => setMoverPeriod(p)}
                className={`px-2 py-0.5 text-xs font-medium rounded transition-colors ${
                  moverPeriod === p
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                }`}
              >
                {p.toUpperCase()}
              </button>
            ))}
          </div>
        );

        if (isLoadingMovers && moverPeriod !== '1d') {
          return (
            <div className="bg-card rounded-lg border p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold">Stijgers & Dalers</span>
                {periodButtons}
              </div>
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            </div>
          );
        }

        if (topGainers.length === 0 && topLosers.length === 0) {
          return (
            <div className="bg-card rounded-lg border p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold">Stijgers & Dalers</span>
                {periodButtons}
              </div>
              <p className="text-sm text-muted-foreground text-center py-4">Geen data beschikbaar</p>
            </div>
          );
        }

        return (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-muted-foreground">Stijgers & Dalers ({periodLabel})</span>
              {periodButtons}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {topGainers.length > 0 && (
                <div className="bg-card rounded-lg border p-4">
                  <h3 className="text-sm font-semibold text-green-500 mb-3 flex items-center gap-1.5">
                    <TrendingUp className="h-4 w-4" /> Stijgers
                  </h3>
                  <div className="space-y-2">
                    {topGainers.map(h => (
                      <Link key={`${h.ticker}-${h.broker || ''}`} to={`/stock/${h.ticker}`}
                        className="flex items-center justify-between hover:bg-muted/50 rounded px-2 py-1.5 -mx-2 transition-colors">
                        <div>
                          <span className="font-medium text-sm">{h.name}</span>
                          <span className="text-xs text-muted-foreground ml-2">{h.ticker}</span>
                        </div>
                        <span className="text-green-500 font-medium text-sm">+{h.change_percent.toFixed(2)}%</span>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
              {topLosers.length > 0 && (
                <div className="bg-card rounded-lg border p-4">
                  <h3 className="text-sm font-semibold text-red-500 mb-3 flex items-center gap-1.5">
                    <TrendingDown className="h-4 w-4" /> Dalers
                  </h3>
                  <div className="space-y-2">
                    {topLosers.map(h => (
                      <Link key={`${h.ticker}-${h.broker || ''}`} to={`/stock/${h.ticker}`}
                        className="flex items-center justify-between hover:bg-muted/50 rounded px-2 py-1.5 -mx-2 transition-colors">
                        <div>
                          <span className="font-medium text-sm">{h.name}</span>
                          <span className="text-xs text-muted-foreground ml-2">{h.ticker}</span>
                        </div>
                        <span className="text-red-500 font-medium text-sm">{h.change_percent.toFixed(2)}%</span>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })()}

      {/* EUR Holdings Table */}
      {eurHoldings.length > 0 && (
        <HoldingsTable
          title="EUR Holdings"
          holdings={sortedEurHoldings}
          isUsd={false}
          sortField={eurSortField}
          sortDir={eurSortDir}
          onToggleSort={toggleEurSort}
          isRefetching={isRefetching}
          onRefetch={() => refetch()}
        />
      )}

      {/* USD Holdings Table */}
      {usdHoldings.length > 0 && (
        <HoldingsTable
          title="USD Holdings"
          holdings={sortedUsdHoldings}
          isUsd={true}
          sortField={usdSortField}
          sortDir={usdSortDir}
          onToggleSort={toggleUsdSort}
          isRefetching={isRefetching}
          onRefetch={() => refetch()}
        />
      )}
    </div>
  );
}

function SummaryCard({
  title,
  value,
  trend,
  subtitle,
  icon,
}: {
  title: string;
  value: string;
  trend?: 'up' | 'down';
  subtitle?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="bg-card rounded-lg border p-4">
      <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
        {icon}
        {title}
      </div>
      <div className="flex items-center gap-2 mt-1">
        <span className={`text-xl font-bold ${
          trend === 'up' ? 'text-green-500' : trend === 'down' ? 'text-red-500' : ''
        }`}>
          {value}
        </span>
        {trend === 'up' && <TrendingUp className="h-4 w-4 text-green-500" />}
        {trend === 'down' && <TrendingDown className="h-4 w-4 text-red-500" />}
      </div>
      {subtitle && (
        <div className="text-xs text-muted-foreground mt-1">{subtitle}</div>
      )}
    </div>
  );
}
