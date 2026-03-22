import { useState, useEffect } from 'react';
import { usePortfolio, useMovers, useCreateStock, useCreateTransaction, useBrokers, useCashSummary, useBrokerDetails } from '@/hooks/usePortfolio';
import { Link, useSearchParams } from 'react-router-dom';
import { TrendingUp, TrendingDown, Loader2, Plus, X, RefreshCw, Hand, Zap, DollarSign, Wallet, ArrowUpDown, ChevronUp, ChevronDown } from 'lucide-react';
import {
  AreaChart, Area, ResponsiveContainer, Tooltip,
  XAxis, YAxis, CartesianGrid
} from 'recharts';
import type { StockInfoCreate, PortfolioHolding } from '@/types';
import { searchStocks, refreshPrices, getPortfolioEvolution } from '@/api/client';
import { formatCurrency, formatPercent, getTodayISO, getCurrencySymbol, getManualPriceAgeColor } from '@/utils/formatting';
import DateInput from '@/components/DateInput';

import { useQueryClient } from '@tanstack/react-query';

type SortField = 'name' | 'quantity' | 'avg_purchase_price' | 'current_price' | 'current_value_eur' | 'total_invested_eur' | 'gain_loss' | 'gain_loss_percent' | 'change_percent' | 'broker' | 'price_updated_at';
type SortDir = 'asc' | 'desc';

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

function formatPriceUpdatedAt(isoStr: string | null): { text: string; colorClass: string } {
  if (!isoStr) return { text: '-', colorClass: 'text-muted-foreground' };
  const updated = new Date(isoStr);
  const now = new Date();
  const hoursAgo = (now.getTime() - updated.getTime()) / (1000 * 60 * 60);
  const text = updated.toLocaleString('nl-BE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  let colorClass = 'text-green-500';
  if (hoursAgo > 24) colorClass = 'text-red-500';
  else if (hoursAgo > 12) colorClass = 'text-orange-500';
  return { text, colorClass };
}

export default function Dashboard() {
  const { data, isLoading, error, refetch, isRefetching } = usePortfolio();
  const { data: brokers } = useBrokers();
  const { data: cashSummary } = useCashSummary();
  const { data: brokerDetails } = useBrokerDetails();
  const createStock = useCreateStock();
  const createTransaction = useCreateTransaction();
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
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSearchResults, setShowSearchResults] = useState(false);
  const [newStock, setNewStock] = useState<StockInfoCreate>({
    ticker: '',
    isin: '',
    name: '',
    asset_type: 'STOCK',
    country: 'Verenigde Staten',
    yahoo_ticker: null,
    manual_price_tracking: false,
    pays_dividend: false,
  });
  const [transaction, setTransaction] = useState({
    date: getTodayISO(),
    broker: 'DEGIRO',
    quantity: 0,
    price_per_share: 0,
    fees: 0,
    taxes: 0,
    exchange_rate: 1.0,
  });
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);
  const [currency, setCurrency] = useState('USD');
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
  const accountTypeMap: Record<string, string> = {};
  brokerDetails?.forEach(b => {
    accountTypeMap[b.broker_name] = b.account_type || 'Privé';
  });

  // Filter brokers by selected account type
  const filteredBrokerNames = selectedAccountType === 'all'
    ? (brokers ?? [])
    : (brokers ?? []).filter(b => accountTypeMap[b] === selectedAccountType);

  const [evolutionData, setEvolutionData] = useState<{ date: string; gain: number; invested: number; value: number }[]>([]);

  useEffect(() => {
    const broker = selectedBroker === 'all' ? undefined : selectedBroker;
    getPortfolioEvolution(broker).then(setEvolutionData).catch(() => {});
  }, [selectedBroker]);

  // Mover period state (must be before early returns)
  const [moverPeriod, setMoverPeriod] = useState<string>('1d');
  const { data: moversData, isLoading: isLoadingMovers } = useMovers(moverPeriod);

  // Sort state for EUR and USD tables (must be before early returns)
  const [eurSortField, setEurSortField] = useState<SortField>('gain_loss');
  const [eurSortDir, setEurSortDir] = useState<SortDir>('desc');
  const [usdSortField, setUsdSortField] = useState<SortField>('gain_loss');
  const [usdSortDir, setUsdSortDir] = useState<SortDir>('desc');

  const handleSearch = async (query: string) => {
    setSearchQuery(query);
    if (query.length < 2) {
      setSearchResults([]);
      setShowSearchResults(false);
      return;
    }

    setIsSearching(true);
    try {
      const results = await searchStocks(query);
      setSearchResults(results);
      setShowSearchResults(true);
    } catch (err) {
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const selectSearchResult = (result: any) => {
    setNewStock({
      ...newStock,
      ticker: result.ticker,
      isin: result.isin || '',
      name: result.name,
      country: result.country || 'Onbekend',
      asset_type: result.asset_type || 'STOCK',
      yahoo_ticker: result.yahoo_ticker,
      manual_price_tracking: result.manual_price_tracking || false,
      pays_dividend: result.pays_dividend || false,
    });

    // Set currency based on result (default EUR for European stocks)
    const stockCurrency = result.currency || (result.country === 'België' || result.country === 'Nederland' || result.country === 'Duitsland' || result.country === 'Frankrijk' ? 'EUR' : 'USD');
    setCurrency(stockCurrency);

    // Set price info if available
    if (result.current_price) {
      setCurrentPrice(result.current_price);
      setTransaction(prev => ({ ...prev, price_per_share: result.current_price }));
    }

    setSearchQuery('');
    setSearchResults([]);
    setShowSearchResults(false);
  };

  const handleAddStock = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      // Try to create the stock (ignore error if already exists)
      try {
        await createStock.mutateAsync(newStock);
      } catch (err: any) {
        // If stock already exists, continue to add transaction
        if (!err?.response?.status || err.response.status !== 400) {
          throw err;
        }
      }

      // Create the transaction if quantity > 0
      if (transaction.quantity > 0) {
        await createTransaction.mutateAsync({
          date: transaction.date,
          broker: transaction.broker,
          transaction_type: 'BUY',
          name: newStock.name,
          ticker: newStock.ticker,
          isin: newStock.isin,
          quantity: transaction.quantity,
          price_per_share: transaction.price_per_share,
          currency: currency,
          fees: transaction.fees,
          taxes: transaction.taxes,
          exchange_rate: transaction.exchange_rate,
          fees_currency: 'EUR',
          notes: null,
        });
      }

      setShowAddStock(false);
      setNewStock({
        ticker: '',
        isin: '',
        name: '',
        asset_type: 'STOCK',
        country: 'Verenigde Staten',
        yahoo_ticker: null,
        manual_price_tracking: false,
        pays_dividend: false,
      });
      setTransaction({
        date: getTodayISO(),
        broker: 'DEGIRO',
        quantity: 0,
        price_per_share: 0,
        fees: 0,
        taxes: 0,
        exchange_rate: 1.0,
      });
      setCurrentPrice(null);
      setSearchQuery('');
      setSearchResults([]);
      setShowSearchResults(false);
    } catch (error) {
      console.error('Failed to add stock:', error);
    }
  };

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
  const filteredSummary = isAllUnfiltered
    ? summary
    : (() => {
        const total_invested_eur = filteredHoldings.reduce((sum, h) => sum + h.total_invested_eur, 0);
        const total_current_value_eur = filteredHoldings.reduce((sum, h) => sum + (h.current_value_eur ?? 0), 0);
        const total_gain_loss_eur = filteredHoldings.reduce((sum, h) => sum + (h.gain_loss ?? 0), 0);
        const total_gain_loss_percent = total_invested_eur > 0
          ? (total_gain_loss_eur / total_invested_eur) * 100
          : 0;
        return { total_invested_eur, total_current_value_eur, total_gain_loss_eur, total_gain_loss_percent };
      })();

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
      else if (field === 'price_updated_at') { av = a.price_updated_at ?? ''; bv = b.price_updated_at ?? ''; }
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
  const sortedEurHoldings = sortHoldings(eurHoldings, eurSortField, eurSortDir);
  const sortedUsdHoldings = sortHoldings(usdHoldings, usdSortField, usdSortDir);

  // Currency-split summaries
  const hasUsd = usdHoldings.length > 0;
  const hasEur = eurHoldings.length > 0;
  const eurSummary = {
    invested: eurHoldings.reduce((sum, h) => sum + h.total_invested_eur, 0),
    value: eurHoldings.reduce((sum, h) => sum + (h.current_value_eur ?? 0), 0),
  };
  const usdSummary = {
    invested: usdHoldings.reduce((sum, h) => sum + h.total_invested, 0),
    value: usdHoldings.reduce((sum, h) => sum + (h.current_value ?? 0), 0),
    invested_eur: usdHoldings.reduce((sum, h) => sum + h.total_invested_eur, 0),
    value_eur: usdHoldings.reduce((sum, h) => sum + (h.current_value_eur ?? 0), 0),
  };

  return (
    <div className="space-y-8">
      {/* Add Stock Modal */}
      {showAddStock && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto py-8">
          <div className="bg-card rounded-lg border p-6 w-full max-w-lg mx-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">Aandeel Toevoegen</h3>
              <button onClick={() => setShowAddStock(false)} className="text-muted-foreground hover:text-foreground">
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleAddStock} className="space-y-4">
              {/* Search stocks */}
              <div className="relative">
                <label className="block text-sm font-medium mb-1">Zoek aandeel</label>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => handleSearch(e.target.value)}
                  onBlur={() => setTimeout(() => setShowSearchResults(false), 200)}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                  placeholder="Zoek op naam, ticker of ISIN..."
                />
                {isSearching && (
                  <Loader2 className="absolute right-3 top-9 h-4 w-4 animate-spin text-muted-foreground" />
                )}
                {showSearchResults && searchResults.length > 0 && (
                  <div className="absolute z-10 w-full mt-1 bg-card border rounded-md shadow-lg max-h-60 overflow-auto">
                    {searchResults.map((result, index) => (
                      <button
                        key={`${result.ticker}-${index}`}
                        type="button"
                        onClick={() => selectSearchResult(result)}
                        className="w-full px-3 py-2 text-left hover:bg-accent border-b last:border-b-0"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium">{result.name}</span>
                          <div className="flex gap-1">
                            {result.pays_dividend && (
                              <span className="text-xs bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 px-2 py-0.5 rounded">Dividend</span>
                            )}
                            {result.from_yahoo && (
                              <span className="text-xs bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 px-2 py-0.5 rounded">Yahoo</span>
                            )}
                          </div>
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {result.ticker} {result.isin && `• ${result.isin}`}
                          {result.current_price && ` • ${getCurrencySymbol(result.currency)}${result.current_price.toFixed(2)}`}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Auto-filled fields */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Ticker *
                    <span className="text-xs text-muted-foreground font-normal ml-1">
                      (bijv. VWCE.DE voor XETRA)
                    </span>
                  </label>
                  <input
                    type="text"
                    value={newStock.ticker}
                    onChange={(e) => setNewStock({ ...newStock, ticker: e.target.value.toUpperCase() })}
                    className="w-full px-3 py-2 border rounded-md bg-background"
                    placeholder="AAPL of VWCE.DE"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">ISIN</label>
                  <input
                    type="text"
                    value={newStock.isin}
                    onChange={(e) => setNewStock({ ...newStock, isin: e.target.value.toUpperCase() })}
                    className="w-full px-3 py-2 border rounded-md bg-background"
                    placeholder="US0378331005"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Type</label>
                  <select
                    value={newStock.asset_type}
                    onChange={(e) => setNewStock({ ...newStock, asset_type: e.target.value as 'STOCK' | 'REIT' | 'FUND' })}
                    className="w-full px-3 py-2 border rounded-md bg-background"
                  >
                    <option value="STOCK">Stock</option>
                    <option value="REIT">REIT</option>
                    <option value="FUND">Fonds</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Valuta</label>
                  <select
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value)}
                    className="w-full px-3 py-2 border rounded-md bg-background"
                  >
                    <option value="EUR">EUR (€)</option>
                    <option value="USD">USD ($)</option>
                    <option value="GBP">GBP (£)</option>
                    <option value="CHF">CHF (Fr)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Land</label>
                  <input
                    type="text"
                    value={newStock.country}
                    onChange={(e) => setNewStock({ ...newStock, country: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md bg-background"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Naam *</label>
                <input
                  type="text"
                  value={newStock.name}
                  onChange={(e) => setNewStock({ ...newStock, name: e.target.value })}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                  placeholder="Apple Inc."
                  required
                />
              </div>

              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="pays_dividend"
                    checked={newStock.pays_dividend}
                    onChange={(e) => setNewStock({ ...newStock, pays_dividend: e.target.checked })}
                    className="w-4 h-4 rounded border-gray-300"
                  />
                  <label htmlFor="pays_dividend" className="text-sm font-medium">
                    Keert dividend uit
                  </label>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="manual_price_tracking"
                    checked={newStock.manual_price_tracking}
                    onChange={(e) => setNewStock({ ...newStock, manual_price_tracking: e.target.checked })}
                    className="w-4 h-4 rounded border-gray-300"
                  />
                  <label htmlFor="manual_price_tracking" className="text-sm font-medium">
                    Handmatig koersen bijhouden
                  </label>
                </div>
              </div>
              {newStock.manual_price_tracking && (
                <p className="text-sm text-muted-foreground -mt-2">
                  Je kunt koersen handmatig invoeren op de stock detail pagina.
                </p>
              )}

              {currentPrice && !newStock.manual_price_tracking && (
                <div className="text-sm text-muted-foreground">
                  Huidige prijs: {getCurrencySymbol(currency)}{currentPrice.toFixed(2)} {currency}
                </div>
              )}

              {/* Transaction Section */}
              <div className="border-t pt-4 mt-4">
                <h4 className="font-medium mb-3">Eerste Aankoop (optioneel)</h4>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Datum</label>
                    <DateInput
                      value={transaction.date}
                      onChange={(date) => setTransaction({ ...transaction, date })}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Broker</label>
                    <select
                      value={transaction.broker}
                      onChange={(e) => setTransaction({ ...transaction, broker: e.target.value })}
                      className="w-full px-3 py-2 border rounded-md bg-background"
                    >
                      {brokers?.map((broker) => (
                        <option key={broker} value={broker}>{broker}</option>
                      )) || (
                        <>
                          <option value="DEGIRO">DEGIRO</option>
                          <option value="IBKR">IBKR</option>
                        </>
                      )}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 mt-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">Aantal</label>
                    <input
                      type="number"
                      value={transaction.quantity || ''}
                      onChange={(e) => setTransaction({ ...transaction, quantity: parseFloat(e.target.value) || 0 })}
                      className="w-full px-3 py-2 border rounded-md bg-background"
                      min="0"
                      step="any"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Prijs per stuk ({currency})</label>
                    <input
                      type="number"
                      step="0.01"
                      value={transaction.price_per_share || ''}
                      onChange={(e) => setTransaction({ ...transaction, price_per_share: parseFloat(e.target.value) || 0 })}
                      className="w-full px-3 py-2 border rounded-md bg-background"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4 mt-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">Kosten (€)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={transaction.fees || ''}
                      onChange={(e) => setTransaction({ ...transaction, fees: parseFloat(e.target.value) || 0 })}
                      className="w-full px-3 py-2 border rounded-md bg-background"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Belasting (€)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={transaction.taxes || ''}
                      onChange={(e) => setTransaction({ ...transaction, taxes: parseFloat(e.target.value) || 0 })}
                      className="w-full px-3 py-2 border rounded-md bg-background"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Wisselkoers</label>
                    <input
                      type="number"
                      step="0.0001"
                      value={transaction.exchange_rate}
                      onChange={(e) => setTransaction({ ...transaction, exchange_rate: parseFloat(e.target.value) || 1 })}
                      className="w-full px-3 py-2 border rounded-md bg-background"
                    />
                  </div>
                </div>

                {transaction.quantity > 0 && transaction.price_per_share > 0 && (
                  <div className="mt-3 p-3 bg-muted rounded-md text-sm">
                    <div className="flex justify-between">
                      <span>Totaal:</span>
                      <span className="font-medium">
                        {getCurrencySymbol(currency)}
                        {(transaction.quantity * transaction.price_per_share).toFixed(2)}
                      </span>
                    </div>
                    {currency === 'USD' && transaction.exchange_rate !== 1 && (
                      <div className="flex justify-between text-muted-foreground">
                        <span>In EUR:</span>
                        <span>{getCurrencySymbol('EUR')}{(transaction.quantity * transaction.price_per_share * transaction.exchange_rate).toFixed(2)}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddStock(false)}
                  className="flex-1 px-4 py-2 border rounded-md hover:bg-accent"
                >
                  Annuleren
                </button>
                <button
                  type="submit"
                  disabled={createStock.isPending || createTransaction.isPending}
                  className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
                >
                  {(createStock.isPending || createTransaction.isPending) ? 'Toevoegen...' : 'Toevoegen'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

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
        <div className="bg-card rounded-lg border">
          <div className="p-6 border-b flex justify-between items-center">
            <h3 className="text-lg font-semibold">EUR Holdings</h3>
            <button
              onClick={() => refetch()}
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
                  <SortHeader field="name" label="Aandeel" sortField={eurSortField} sortDir={eurSortDir} onToggle={toggleEurSort} align="left" />
                  <th className="text-center p-4 font-medium" title="Dividend">
                    <DollarSign className="h-4 w-4 inline" />
                  </th>
                  <SortHeader field="quantity" label="Aantal" sortField={eurSortField} sortDir={eurSortDir} onToggle={toggleEurSort} />
                  <SortHeader field="avg_purchase_price" label="Aankoop" sortField={eurSortField} sortDir={eurSortDir} onToggle={toggleEurSort} />
                  <SortHeader field="current_price" label="Huidig" sortField={eurSortField} sortDir={eurSortDir} onToggle={toggleEurSort} />
                  <SortHeader field="current_value_eur" label="Waarde" sortField={eurSortField} sortDir={eurSortDir} onToggle={toggleEurSort} />
                  <SortHeader field="total_invested_eur" label="Geïnvesteerd" sortField={eurSortField} sortDir={eurSortDir} onToggle={toggleEurSort} />
                  <SortHeader field="gain_loss" label="W/V" sortField={eurSortField} sortDir={eurSortDir} onToggle={toggleEurSort} />
                  <SortHeader field="gain_loss_percent" label="%" sortField={eurSortField} sortDir={eurSortDir} onToggle={toggleEurSort} />
                  <SortHeader field="change_percent" label="Dag" sortField={eurSortField} sortDir={eurSortDir} onToggle={toggleEurSort} />
                  <SortHeader field="broker" label="Broker" sortField={eurSortField} sortDir={eurSortDir} onToggle={toggleEurSort} align="left" />
                  <SortHeader field="price_updated_at" label="Bijgewerkt" sortField={eurSortField} sortDir={eurSortDir} onToggle={toggleEurSort} />
                </tr>
              </thead>
              <tbody>
                {sortedEurHoldings.map((holding) => {
                  const symbol = getCurrencySymbol('EUR');
                  const priceAge = formatPriceUpdatedAt(holding.price_updated_at);
                  return (
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
                          ? `${symbol}${holding.current_value_eur.toFixed(2)}`
                          : 'N/A'}
                      </td>
                      <td className="text-right p-4">
                        {symbol}{holding.total_invested_eur.toFixed(2)}
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
                      <td className="p-4">{holding.broker}</td>
                      <td className={`text-right p-4 text-xs ${priceAge.colorClass}`}>{priceAge.text}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* USD Holdings Table */}
      {usdHoldings.length > 0 && (
        <div className="bg-card rounded-lg border">
          <div className="p-6 border-b flex justify-between items-center">
            <h3 className="text-lg font-semibold">USD Holdings</h3>
            <button
              onClick={() => refetch()}
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
                  <SortHeader field="name" label="Aandeel" sortField={usdSortField} sortDir={usdSortDir} onToggle={toggleUsdSort} align="left" />
                  <th className="text-center p-4 font-medium" title="Dividend">
                    <DollarSign className="h-4 w-4 inline" />
                  </th>
                  <SortHeader field="quantity" label="Aantal" sortField={usdSortField} sortDir={usdSortDir} onToggle={toggleUsdSort} />
                  <SortHeader field="avg_purchase_price" label="Aankoop" sortField={usdSortField} sortDir={usdSortDir} onToggle={toggleUsdSort} />
                  <SortHeader field="current_price" label="Huidig" sortField={usdSortField} sortDir={usdSortDir} onToggle={toggleUsdSort} />
                  <SortHeader field="current_value_eur" label="Waarde (EUR)" sortField={usdSortField} sortDir={usdSortDir} onToggle={toggleUsdSort} />
                  <SortHeader field="total_invested_eur" label="Geïnvesteerd" sortField={usdSortField} sortDir={usdSortDir} onToggle={toggleUsdSort} />
                  <SortHeader field="gain_loss" label="W/V" sortField={usdSortField} sortDir={usdSortDir} onToggle={toggleUsdSort} />
                  <SortHeader field="gain_loss_percent" label="%" sortField={usdSortField} sortDir={usdSortDir} onToggle={toggleUsdSort} />
                  <SortHeader field="change_percent" label="Dag" sortField={usdSortField} sortDir={usdSortDir} onToggle={toggleUsdSort} />
                  <SortHeader field="broker" label="Broker" sortField={usdSortField} sortDir={usdSortDir} onToggle={toggleUsdSort} align="left" />
                  <SortHeader field="price_updated_at" label="Bijgewerkt" sortField={usdSortField} sortDir={usdSortDir} onToggle={toggleUsdSort} />
                </tr>
              </thead>
              <tbody>
                {sortedUsdHoldings.map((holding) => {
                  const symbol = getCurrencySymbol('USD');
                  const priceAge = formatPriceUpdatedAt(holding.price_updated_at);

                  return (
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
                          ? `${getCurrencySymbol('EUR')}${holding.current_value_eur.toFixed(2)}`
                          : 'N/A'}
                      </td>
                      <td className="text-right p-4">
                        {symbol}{holding.total_invested.toFixed(2)}
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
                      <td className="p-4">{holding.broker}</td>
                      <td className={`text-right p-4 text-xs ${priceAge.colorClass}`}>{priceAge.text}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
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
