import { useParams } from 'react-router-dom';
import { useTransactions, useDividends, useCreateTransaction, useUpdateTransaction, useDeleteTransaction, useCreateDividend, useUpdateDividend, useDeleteDividend, useBrokers, useManualPrices, useCreateManualPrice, useDeleteManualPrice, useStockDetail, useUpdateStock, useStockHistory } from '@/hooks/usePortfolio';
import { useState } from 'react';
import { Loader2, Plus, Trash2, Pencil, X, Check, DollarSign, Download, Settings, TrendingUp } from 'lucide-react';
import type { Transaction, Dividend } from '@/types';
import { formatCurrency, formatDate, getTodayISO, getCurrencySymbol } from '@/utils/formatting';
import DateInput from '@/components/DateInput';
import { fetchDividendHistory } from '@/api/client';
import { useQueryClient } from '@tanstack/react-query';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function StockDetail() {
  const { ticker } = useParams<{ ticker: string }>();
  const queryClient = useQueryClient();
  const { data: transactions, isLoading: loadingTx } = useTransactions(ticker);
  const { data: dividends, isLoading: loadingDiv } = useDividends(ticker);
  const { data: brokers } = useBrokers();
  const { data: stockDetail } = useStockDetail(ticker || '');
  const { data: manualPrices } = useManualPrices(ticker || '');
  const createTransaction = useCreateTransaction();
  const updateTransaction = useUpdateTransaction();
  const deleteTransaction = useDeleteTransaction();
  const createDividend = useCreateDividend();
  const updateDividend = useUpdateDividend();
  const deleteDividend = useDeleteDividend();
  const createManualPrice = useCreateManualPrice();
  const deleteManualPrice = useDeleteManualPrice();
  const updateStock = useUpdateStock();

  const [showTxForm, setShowTxForm] = useState(false);
  const [showDivForm, setShowDivForm] = useState(false);
  const [showPriceForm, setShowPriceForm] = useState(false);
  const [showStockSettings, setShowStockSettings] = useState(false);
  const [editingTxId, setEditingTxId] = useState<number | null>(null);
  const [editingDivId, setEditingDivId] = useState<number | null>(null);
  const [fetchingDividends, setFetchingDividends] = useState(false);
  const [historyPeriod, setHistoryPeriod] = useState('1y');

  // Check if manual price tracking is enabled
  const isManualPriceTracking = stockDetail?.info?.manual_price_tracking;

  // Get historical data
  const { data: historyData, isLoading: loadingHistory } = useStockHistory(ticker || '', historyPeriod);

  // Get first transaction for default values
  const firstTx = transactions?.[0];

  const getEmptyTxForm = () => ({
    date: getTodayISO(),
    broker: firstTx?.broker || 'DEGIRO',
    transaction_type: 'BUY' as 'BUY' | 'SELL',
    name: firstTx?.name || '',
    ticker: ticker || '',
    isin: firstTx?.isin || '',
    quantity: 0,
    price_per_share: 0,
    currency: firstTx?.currency || 'USD',
    fees: 0,
    taxes: 0,
    exchange_rate: 1.0,
    fees_currency: 'EUR',
    notes: null as string | null,
  });

  const getEmptyDivForm = () => ({
    ticker: ticker || '',
    isin: firstTx?.isin || '',
    ex_date: getTodayISO(),
    bruto_amount: 0,
    currency: 'USD',
    withheld_tax: 0,
    net_amount: null as number | null,
    received: false,
    notes: null as string | null,
  });

  const [txForm, setTxForm] = useState(getEmptyTxForm());
  const [divForm, setDivForm] = useState(getEmptyDivForm());
  const [taxPercentage, setTaxPercentage] = useState(30); // Default 30% for Belgium

  // Auto-calculate tax amounts when bruto_amount or percentage changes
  const handleBrutoAmountChange = (bruto: number) => {
    const withheld = bruto * (taxPercentage / 100);
    const net = bruto - withheld;
    setDivForm({
      ...divForm,
      bruto_amount: bruto,
      withheld_tax: parseFloat(withheld.toFixed(2)),
      net_amount: parseFloat(net.toFixed(2))
    });
  };

  const handleTaxPercentageChange = (percentage: number) => {
    setTaxPercentage(percentage);
    const withheld = divForm.bruto_amount * (percentage / 100);
    const net = divForm.bruto_amount - withheld;
    setDivForm({
      ...divForm,
      withheld_tax: parseFloat(withheld.toFixed(2)),
      net_amount: parseFloat(net.toFixed(2))
    });
  };

  const getEmptyPriceForm = () => ({
    ticker: ticker || '',
    date: getTodayISO(),
    price: 0,
    currency: firstTx?.currency || 'EUR',
    notes: null as string | null,
  });

  const [priceForm, setPriceForm] = useState(getEmptyPriceForm());

  const [stockSettingsForm, setStockSettingsForm] = useState({
    manual_price_tracking: false,
    pays_dividend: false,
  });

  const handleUpdateStockSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (ticker && stockDetail?.info) {
      await updateStock.mutateAsync({
        ticker,
        stock: {
          ticker,
          isin: stockDetail.info.isin,
          name: stockDetail.info.name,
          asset_type: stockDetail.info.asset_type,
          country: stockDetail.info.country,
          yahoo_ticker: stockDetail.info.yahoo_ticker,
          manual_price_tracking: stockSettingsForm.manual_price_tracking,
          pays_dividend: stockSettingsForm.pays_dividend,
        },
      });
      setShowStockSettings(false);
    }
  };

  const handleCreateTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    await createTransaction.mutateAsync(txForm);
    setShowTxForm(false);
    setTxForm(getEmptyTxForm());
  };

  const handleUpdateTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (editingTxId) {
      await updateTransaction.mutateAsync({ id: editingTxId, data: txForm });
      setEditingTxId(null);
      setTxForm(getEmptyTxForm());
    }
  };

  const startEditTransaction = (tx: Transaction) => {
    setEditingTxId(tx.id);
    setTxForm({
      date: tx.date,
      broker: tx.broker,
      transaction_type: tx.transaction_type,
      name: tx.name,
      ticker: tx.ticker,
      isin: tx.isin,
      quantity: tx.quantity,
      price_per_share: tx.price_per_share,
      currency: tx.currency,
      fees: tx.fees,
      taxes: tx.taxes,
      exchange_rate: tx.exchange_rate,
      fees_currency: tx.fees_currency,
      notes: tx.notes,
    });
    setShowTxForm(false);
  };

  const handleCreateDividend = async (e: React.FormEvent) => {
    e.preventDefault();
    await createDividend.mutateAsync(divForm);
    setShowDivForm(false);
    setDivForm(getEmptyDivForm());
    setTaxPercentage(30);
  };

  const handleUpdateDividend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (editingDivId) {
      await updateDividend.mutateAsync({ id: editingDivId, data: divForm });
      setEditingDivId(null);
      setDivForm(getEmptyDivForm());
      setTaxPercentage(30);
    }
  };

  const startEditDividend = (div: Dividend) => {
    setEditingDivId(div.id);

    // Calculate percentage from existing values
    let calculatedPercentage = 30; // Default
    if (div.bruto_amount > 0 && div.withheld_tax > 0) {
      calculatedPercentage = parseFloat(((div.withheld_tax / div.bruto_amount) * 100).toFixed(1));
    }
    setTaxPercentage(calculatedPercentage);

    // Recalculate withheld and net amounts based on bruto and percentage
    const withheld = div.bruto_amount * (calculatedPercentage / 100);
    const net = div.bruto_amount - withheld;

    setDivForm({
      ticker: div.ticker,
      isin: div.isin,
      ex_date: div.ex_date,
      bruto_amount: div.bruto_amount,
      currency: div.currency,
      withheld_tax: parseFloat(withheld.toFixed(2)),
      net_amount: parseFloat(net.toFixed(2)),
      received: div.received,
      notes: div.notes,
    });
    setShowDivForm(false);
  };

  const handleFetchDividendHistory = async () => {
    if (!ticker) return;

    setFetchingDividends(true);
    try {
      const result = await fetchDividendHistory(ticker);
      await queryClient.invalidateQueries({ queryKey: ['dividends', ticker] });
      alert(`${result.count} dividenden toegevoegd (${result.total_found} gevonden)`);
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Fout bij ophalen dividenden');
    } finally {
      setFetchingDividends(false);
    }
  };

  const handleCreatePrice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (ticker) {
      await createManualPrice.mutateAsync({ ticker, data: priceForm });
      setShowPriceForm(false);
      setPriceForm(getEmptyPriceForm());
    }
  };

  if (loadingTx || loadingDiv) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">{ticker}</h1>
      {firstTx && (
        <p className="text-muted-foreground">{firstTx.name} • {firstTx.isin}</p>
      )}

      {/* Stock Settings */}
      <div className="bg-card rounded-lg border">
        <div className="p-6 border-b flex justify-between items-center">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Instellingen
          </h3>
          {!showStockSettings && (
            <button
              onClick={() => {
                setShowStockSettings(true);
                setStockSettingsForm({
                  manual_price_tracking: stockDetail?.info?.manual_price_tracking || false,
                  pays_dividend: stockDetail?.info?.pays_dividend || false,
                });
              }}
              className="flex items-center gap-2 px-3 py-2 border rounded-md hover:bg-accent"
            >
              <Pencil className="h-4 w-4" /> Bewerken
            </button>
          )}
        </div>

        {showStockSettings && stockDetail?.info ? (
          <form onSubmit={handleUpdateStockSettings} className="p-6 bg-muted/50 space-y-4">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="manual_price_tracking"
                checked={stockSettingsForm.manual_price_tracking}
                onChange={(e) => setStockSettingsForm({ ...stockSettingsForm, manual_price_tracking: e.target.checked })}
                className="w-4 h-4 rounded border-gray-300"
              />
              <label htmlFor="manual_price_tracking" className="text-sm font-medium">
                Handmatig koersen bijhouden
              </label>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="pays_dividend_edit"
                checked={stockSettingsForm.pays_dividend}
                onChange={(e) => setStockSettingsForm({ ...stockSettingsForm, pays_dividend: e.target.checked })}
                className="w-4 h-4 rounded border-gray-300"
              />
              <label htmlFor="pays_dividend_edit" className="text-sm font-medium">
                Keert dividend uit
              </label>
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={updateStock.isPending}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
              >
                {updateStock.isPending ? 'Opslaan...' : 'Opslaan'}
              </button>
              <button
                type="button"
                onClick={() => setShowStockSettings(false)}
                className="px-4 py-2 border rounded-md hover:bg-accent"
              >
                Annuleren
              </button>
            </div>
          </form>
        ) : (
          <div className="p-6 space-y-2">
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">
                Handmatig koersen bijhouden: <strong>{stockDetail?.info?.manual_price_tracking ? 'Ja' : 'Nee'}</strong>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">
                Keert dividend uit: <strong>{stockDetail?.info?.pays_dividend ? 'Ja' : 'Nee'}</strong>
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Price History Chart */}
      <div className="bg-card rounded-lg border">
        <div className="p-6 border-b flex justify-between items-center">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Koersverloop
          </h3>
          <select
            value={historyPeriod}
            onChange={(e) => setHistoryPeriod(e.target.value)}
            className="px-3 py-1.5 text-sm border rounded-md bg-background"
          >
            <option value="1mo">1 Maand</option>
            <option value="3mo">3 Maanden</option>
            <option value="6mo">6 Maanden</option>
            <option value="1y">1 Jaar</option>
            <option value="2y">2 Jaar</option>
            <option value="5y">5 Jaar</option>
            <option value="max">Maximaal</option>
          </select>
        </div>
        <div className="p-6">
          {loadingHistory ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : historyData && historyData.length > 0 ? (
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={historyData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(value) => {
                      const date = new Date(value);
                      return date.toLocaleDateString('nl-NL', { month: 'short', year: '2-digit' });
                    }}
                  />
                  <YAxis
                    domain={['auto', 'auto']}
                    tickFormatter={(value) => `${getCurrencySymbol(firstTx?.currency || 'EUR')}${value.toFixed(2)}`}
                  />
                  <Tooltip
                    formatter={(value: number) => [
                      formatCurrency(value, firstTx?.currency || 'EUR'),
                      'Prijs'
                    ]}
                    labelFormatter={(label) => formatDate(label)}
                  />
                  <Line
                    type="monotone"
                    dataKey="price"
                    stroke="#8884d8"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="text-center text-muted-foreground py-12">
              Geen historische data beschikbaar
            </div>
          )}
        </div>
      </div>

      {/* Transactions */}
      <div className="bg-card rounded-lg border">
        <div className="p-6 border-b flex justify-between items-center">
          <h3 className="text-lg font-semibold">Transacties</h3>
          <button
            onClick={() => {
              setShowTxForm(!showTxForm);
              setEditingTxId(null);
              setTxForm(getEmptyTxForm());
            }}
            className="flex items-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" /> Toevoegen
          </button>
        </div>

        {(showTxForm || editingTxId) && (
          <form onSubmit={editingTxId ? handleUpdateTransaction : handleCreateTransaction} className="p-6 border-b bg-muted/50 space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-xs font-medium mb-1">Datum</label>
                <DateInput
                  value={txForm.date}
                  onChange={(date) => setTxForm({ ...txForm, date })}
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Type</label>
                <select
                  value={txForm.transaction_type}
                  onChange={(e) => setTxForm({ ...txForm, transaction_type: e.target.value as 'BUY' | 'SELL' })}
                  className="w-full px-3 py-2 rounded-md border bg-background"
                >
                  <option value="BUY">Koop</option>
                  <option value="SELL">Verkoop</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Aantal</label>
                <input
                  type="number"
                  value={txForm.quantity || ''}
                  onChange={(e) => setTxForm({ ...txForm, quantity: parseInt(e.target.value) || 0 })}
                  className="w-full px-3 py-2 rounded-md border bg-background"
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Prijs</label>
                <input
                  type="number"
                  step="0.01"
                  value={txForm.price_per_share || ''}
                  onChange={(e) => setTxForm({ ...txForm, price_per_share: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 rounded-md border bg-background"
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Broker</label>
                <select
                  value={txForm.broker}
                  onChange={(e) => setTxForm({ ...txForm, broker: e.target.value })}
                  className="w-full px-3 py-2 rounded-md border bg-background"
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
              <div>
                <label className="block text-xs font-medium mb-1">Valuta</label>
                <select
                  value={txForm.currency}
                  onChange={(e) => setTxForm({ ...txForm, currency: e.target.value })}
                  className="w-full px-3 py-2 rounded-md border bg-background"
                >
                  <option value="EUR">EUR</option>
                  <option value="USD">USD</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Wisselkoers</label>
                <input
                  type="number"
                  step="0.0001"
                  value={txForm.exchange_rate || ''}
                  onChange={(e) => setTxForm({ ...txForm, exchange_rate: parseFloat(e.target.value) || 1 })}
                  className="w-full px-3 py-2 rounded-md border bg-background"
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Kosten (€)</label>
                <input
                  type="number"
                  step="0.01"
                  value={txForm.fees || ''}
                  onChange={(e) => setTxForm({ ...txForm, fees: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 rounded-md border bg-background"
                  placeholder="0.00"
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Belasting (€)</label>
                <input
                  type="number"
                  step="0.01"
                  value={txForm.taxes || ''}
                  onChange={(e) => setTxForm({ ...txForm, taxes: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 rounded-md border bg-background"
                  placeholder="0.00"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
              >
                {editingTxId ? 'Bijwerken' : 'Opslaan'}
              </button>
              {editingTxId && (
                <button
                  type="button"
                  onClick={() => {
                    setEditingTxId(null);
                    setTxForm(getEmptyTxForm());
                  }}
                  className="px-4 py-2 border rounded-md hover:bg-accent"
                >
                  Annuleren
                </button>
              )}
            </div>
          </form>
        )}

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="text-left p-4 font-medium">Datum</th>
                <th className="text-left p-4 font-medium">Type</th>
                <th className="text-right p-4 font-medium">Aantal</th>
                <th className="text-right p-4 font-medium">Prijs</th>
                <th className="text-right p-4 font-medium">Totaal</th>
                <th className="text-right p-4 font-medium">Kosten</th>
                <th className="text-right p-4 font-medium">Belasting</th>
                <th className="text-left p-4 font-medium">Broker</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody>
              {transactions?.map((tx) => (
                <tr key={tx.id} className="border-b hover:bg-muted/50">
                  <td className="p-4">{formatDate(tx.date)}</td>
                  <td className="p-4">
                    <span className={tx.transaction_type === 'BUY' ? 'text-green-500' : 'text-red-500'}>
                      {tx.transaction_type === 'BUY' ? 'Koop' : 'Verkoop'}
                    </span>
                  </td>
                  <td className="text-right p-4">{tx.quantity}</td>
                  <td className="text-right p-4">{formatCurrency(tx.price_per_share, tx.currency)}</td>
                  <td className="text-right p-4">{formatCurrency(tx.quantity * tx.price_per_share, tx.currency)}</td>
                  <td className="text-right p-4">{formatCurrency(tx.fees, 'EUR')}</td>
                  <td className="text-right p-4">{formatCurrency(tx.taxes, 'EUR')}</td>
                  <td className="p-4">{tx.broker}</td>
                  <td className="p-4">
                    <div className="flex gap-2">
                      <button
                        onClick={() => startEditTransaction(tx)}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => deleteTransaction.mutate(tx.id)}
                        className="text-destructive hover:text-destructive/80"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Dividends */}
      <div className="bg-card rounded-lg border">
        <div className="p-6 border-b flex justify-between items-center">
          <h3 className="text-lg font-semibold">Dividenden</h3>
          <div className="flex gap-2">
            {stockDetail?.info?.pays_dividend && (
              <button
                onClick={handleFetchDividendHistory}
                disabled={fetchingDividends}
                className="flex items-center gap-2 px-3 py-2 border rounded-md hover:bg-accent transition-colors disabled:opacity-50"
                title="Haal automatisch dividendhistorie op vanaf eerste aankoop"
              >
                {fetchingDividends ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Download className="h-4 w-4" />
                )}
                Importeren
              </button>
            )}
            <button
              onClick={() => {
                setShowDivForm(!showDivForm);
                setEditingDivId(null);
                setDivForm(getEmptyDivForm());
                setTaxPercentage(30); // Reset to default 30%
              }}
              className="flex items-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" /> Toevoegen
            </button>
          </div>
        </div>

        {(showDivForm || editingDivId) && (
          <form onSubmit={editingDivId ? handleUpdateDividend : handleCreateDividend} className="p-6 border-b bg-muted/50 space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
              <div>
                <label className="block text-xs font-medium mb-1">Ex-datum</label>
                <DateInput
                  value={divForm.ex_date}
                  onChange={(date) => setDivForm({ ...divForm, ex_date: date })}
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Bruto bedrag</label>
                <input
                  type="number"
                  step="0.01"
                  value={divForm.bruto_amount || ''}
                  onChange={(e) => handleBrutoAmountChange(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 rounded-md border bg-background"
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Valuta</label>
                <select
                  value={divForm.currency}
                  onChange={(e) => setDivForm({ ...divForm, currency: e.target.value })}
                  className="w-full px-3 py-2 rounded-md border bg-background"
                >
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">
                  Belasting %
                  <span className="ml-1 text-muted-foreground font-normal" title="België: 30%, VS/NL: 15%, GVV: 15%">ⓘ</span>
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  value={taxPercentage || ''}
                  onChange={(e) => handleTaxPercentageChange(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 rounded-md border bg-background"
                  placeholder="30"
                  title="België: 30%, Verenigde Staten: 15%, Nederland: 15%, GVV: 15%"
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Ingehouden (auto)</label>
                <input
                  type="number"
                  step="0.01"
                  value={divForm.withheld_tax || ''}
                  readOnly
                  className="w-full px-3 py-2 rounded-md border bg-muted text-muted-foreground"
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Netto (auto)</label>
                <input
                  type="number"
                  step="0.01"
                  value={divForm.net_amount || ''}
                  readOnly
                  className="w-full px-3 py-2 rounded-md border bg-muted text-muted-foreground"
                />
              </div>
              <div className="flex items-center">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={divForm.received}
                    onChange={(e) => setDivForm({ ...divForm, received: e.target.checked })}
                  />
                  <span className="text-sm">Ontvangen</span>
                </label>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
              >
                {editingDivId ? 'Bijwerken' : 'Opslaan'}
              </button>
              {editingDivId && (
                <button
                  type="button"
                  onClick={() => {
                    setEditingDivId(null);
                    setDivForm(getEmptyDivForm());
                    setTaxPercentage(30);
                  }}
                  className="px-4 py-2 border rounded-md hover:bg-accent"
                >
                  Annuleren
                </button>
              )}
            </div>
          </form>
        )}

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="text-left p-4 font-medium">Ex-datum</th>
                <th className="text-right p-4 font-medium">Per aandeel</th>
                <th className="text-right p-4 font-medium">Bruto totaal</th>
                <th className="text-right p-4 font-medium">Ingehouden</th>
                <th className="text-right p-4 font-medium">Netto</th>
                <th className="text-center p-4 font-medium">Ontvangen</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody>
              {dividends?.map((div) => {
                // Extract dividend per share from notes if auto-imported
                const perShareMatch = div.notes?.match(/€([\d.]+)\/aandeel/);
                const perShare = perShareMatch ? parseFloat(perShareMatch[1]) : null;

                return (
                  <tr key={div.id} className="border-b hover:bg-muted/50">
                    <td className="p-4">{formatDate(div.ex_date)}</td>
                    <td className="text-right p-4 text-muted-foreground text-sm">
                      {perShare ? formatCurrency(perShare, div.currency) : '—'}
                    </td>
                    <td className="text-right p-4 font-medium">{formatCurrency(div.bruto_amount, div.currency)}</td>
                    <td className="text-right p-4">{formatCurrency(div.withheld_tax, div.currency)}</td>
                    <td className="text-right p-4 font-medium">{div.net_amount ? formatCurrency(div.net_amount, div.currency) : '—'}</td>
                    <td className="text-center p-4">
                      {div.received ? <Check className="h-4 w-4 text-green-500 mx-auto" /> : <X className="h-4 w-4 text-muted-foreground mx-auto" />}
                    </td>
                    <td className="p-4">
                      <div className="flex gap-2">
                        <button
                          onClick={() => startEditDividend(div)}
                          className="text-muted-foreground hover:text-foreground"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => deleteDividend.mutate(div.id)}
                          className="text-destructive hover:text-destructive/80"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Manual Prices - only show if manual price tracking is enabled */}
      {isManualPriceTracking && (
        <div className="bg-card rounded-lg border">
          <div className="p-6 border-b flex justify-between items-center">
            <div className="flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-primary" />
              <h3 className="text-lg font-semibold">Handmatige Koersen</h3>
            </div>
            <button
              onClick={() => {
                setShowPriceForm(!showPriceForm);
                setPriceForm(getEmptyPriceForm());
              }}
              className="flex items-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" /> Toevoegen
            </button>
          </div>

          {showPriceForm && (
            <form onSubmit={handleCreatePrice} className="p-6 border-b bg-muted/50 space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-xs font-medium mb-1">Datum</label>
                  <DateInput
                    value={priceForm.date}
                    onChange={(date) => setPriceForm({ ...priceForm, date })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1">Prijs</label>
                  <input
                    type="number"
                    step="0.01"
                    value={priceForm.price || ''}
                    onChange={(e) => setPriceForm({ ...priceForm, price: parseFloat(e.target.value) || 0 })}
                    className="w-full px-3 py-2 rounded-md border bg-background"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1">Valuta</label>
                  <select
                    value={priceForm.currency}
                    onChange={(e) => setPriceForm({ ...priceForm, currency: e.target.value })}
                    className="w-full px-3 py-2 rounded-md border bg-background"
                  >
                    <option value="EUR">EUR</option>
                    <option value="USD">USD</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1">Notities</label>
                  <input
                    type="text"
                    value={priceForm.notes || ''}
                    onChange={(e) => setPriceForm({ ...priceForm, notes: e.target.value || null })}
                    className="w-full px-3 py-2 rounded-md border bg-background"
                    placeholder="Optioneel"
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  type="submit"
                  className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
                >
                  Opslaan
                </button>
                <button
                  type="button"
                  onClick={() => setShowPriceForm(false)}
                  className="px-4 py-2 border rounded-md hover:bg-accent"
                >
                  Annuleren
                </button>
              </div>
            </form>
          )}

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-left p-4 font-medium">Datum</th>
                  <th className="text-right p-4 font-medium">Prijs</th>
                  <th className="text-left p-4 font-medium">Notities</th>
                  <th className="p-4"></th>
                </tr>
              </thead>
              <tbody>
                {manualPrices?.map((price) => (
                  <tr key={price.id} className="border-b hover:bg-muted/50">
                    <td className="p-4">{formatDate(price.date)}</td>
                    <td className="text-right p-4">{formatCurrency(price.price, price.currency)}</td>
                    <td className="p-4 text-muted-foreground">{price.notes || '—'}</td>
                    <td className="p-4">
                      <button
                        onClick={() => ticker && deleteManualPrice.mutate({ ticker, id: price.id })}
                        className="text-destructive hover:text-destructive/80"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
                {(!manualPrices || manualPrices.length === 0) && (
                  <tr>
                    <td colSpan={4} className="p-4 text-center text-muted-foreground">
                      Geen handmatige koersen ingevoerd
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
