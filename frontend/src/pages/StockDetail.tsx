import { useParams } from 'react-router-dom';
import { useTransactions, useDividends, useCreateTransaction, useUpdateTransaction, useDeleteTransaction, useCreateDividend, useUpdateDividend, useDeleteDividend, useBrokers, useManualPrices, useCreateManualPrice, useDeleteManualPrice, useStockDetail, useUpdateStock, useStockHistory, useStockAlerts, useCreateAlert, useUpdateAlert, useDeleteAlert } from '@/hooks/usePortfolio';
import { useState } from 'react';
import { Loader2, Plus, Trash2, Pencil, X, Check, DollarSign, Download, Settings, TrendingUp, Calendar, Bell, ToggleLeft, ToggleRight } from 'lucide-react';
import type { Transaction, Dividend, StockAlertCreate } from '@/types';
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

  const { data: stockAlerts } = useStockAlerts(ticker || '');
  const createAlertMutation = useCreateAlert();
  const updateAlertMutation = useUpdateAlert();
  const deleteAlertMutation = useDeleteAlert();

  const [showAlertForm, setShowAlertForm] = useState(false);
  const [alertForm, setAlertForm] = useState<{
    alert_type: StockAlertCreate['alert_type'];
    period: string;
    threshold_price: string;
  }>({
    alert_type: 'period_high',
    period: '52w',
    threshold_price: '',
  });

  const [showTxForm, setShowTxForm] = useState(false);
  const [showDivForm, setShowDivForm] = useState(false);
  const [showPriceForm, setShowPriceForm] = useState(false);
  const [showStockSettings, setShowStockSettings] = useState(false);
  const [editingTxId, setEditingTxId] = useState<number | null>(null);
  const [editingDivId, setEditingDivId] = useState<number | null>(null);
  const [fetchingDividends, setFetchingDividends] = useState(false);
  const [historyPeriod, setHistoryPeriod] = useState('1y');

  // Inline editing state
  const [inlineEdit, setInlineEdit] = useState<{ txId: number; field: string; value: string } | null>(null);

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
    yahoo_ticker: '',
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
          yahoo_ticker: stockSettingsForm.yahoo_ticker || null,
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

  const saveInlineEdit = async () => {
    if (!inlineEdit) return;
    const tx = transactions?.find((t) => t.id === inlineEdit.txId);
    if (!tx) return;

    const updated: Record<string, any> = { ...tx };
    const { field, value } = inlineEdit;

    if (field === 'date') {
      updated.date = value;
    } else if (field === 'quantity' || field === 'price_per_share' || field === 'fees' || field === 'taxes' || field === 'exchange_rate') {
      updated[field] = parseFloat(value) || 0;
    } else if (field === 'broker' || field === 'transaction_type') {
      updated[field] = value;
    }

    // Remove 'id' from payload
    const { id, ...payload } = updated;
    await updateTransaction.mutateAsync({ id: inlineEdit.txId, data: payload as any });
    setInlineEdit(null);
  };

  const handleInlineKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault();
      saveInlineEdit();
    } else if (e.key === 'Escape') {
      setInlineEdit(null);
    }
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

  const alertTypeOptions = [
    { value: 'period_high', label: '52-week hoog', period: '52w' },
    { value: 'period_high_26', label: '26-week hoog', period: '26w' },
    { value: 'period_high_13', label: '13-week hoog', period: '13w' },
    { value: 'period_low', label: '52-week laag', period: '52w' },
    { value: 'period_low_26', label: '26-week laag', period: '26w' },
    { value: 'period_low_13', label: '13-week laag', period: '13w' },
    { value: 'above', label: 'Prijs boven' },
    { value: 'below', label: 'Prijs onder' },
  ] as const;

  const handleAlertTypeChange = (combined: string) => {
    const option = alertTypeOptions.find(o => o.value === combined);
    if (!option) return;

    const baseType = combined.startsWith('period_high') ? 'period_high'
      : combined.startsWith('period_low') ? 'period_low'
      : combined as StockAlertCreate['alert_type'];

    const period = 'period' in option ? option.period : '';

    setAlertForm({
      alert_type: baseType,
      period,
      threshold_price: alertForm.threshold_price,
    });
  };

  const handleCreateAlert = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker) return;

    const data: StockAlertCreate = {
      ticker,
      alert_type: alertForm.alert_type,
      period: alertForm.alert_type.startsWith('period_') ? alertForm.period : null,
      threshold_price: ['above', 'below'].includes(alertForm.alert_type)
        ? parseFloat(alertForm.threshold_price) || null
        : null,
      enabled: true,
    };

    await createAlertMutation.mutateAsync(data);
    setShowAlertForm(false);
    setAlertForm({ alert_type: 'period_high', period: '52w', threshold_price: '' });
  };

  const handleToggleAlert = async (alert: { id: number; ticker: string; alert_type: StockAlertCreate['alert_type']; period?: string | null; threshold_price?: number | null; enabled: boolean }) => {
    await updateAlertMutation.mutateAsync({
      alertId: alert.id,
      data: {
        ticker: alert.ticker,
        alert_type: alert.alert_type,
        period: alert.period,
        threshold_price: alert.threshold_price,
        enabled: !alert.enabled,
      },
    });
  };

  const getAlertDescription = (alert: { alert_type: string; period?: string | null; threshold_price?: number | null }): string => {
    const periodLabels: Record<string, string> = { '52w': '52-week', '26w': '26-week', '13w': '13-week' };
    const periodLabel = alert.period ? periodLabels[alert.period] || alert.period : '';

    switch (alert.alert_type) {
      case 'period_high': return `${periodLabel} hoog`;
      case 'period_low': return `${periodLabel} laag`;
      case 'above': return `Prijs boven ${getCurrencySymbol(firstTx?.currency || 'EUR')}${alert.threshold_price?.toFixed(2) || '?'}`;
      case 'below': return `Prijs onder ${getCurrencySymbol(firstTx?.currency || 'EUR')}${alert.threshold_price?.toFixed(2) || '?'}`;
      default: return alert.alert_type;
    }
  };

  // Compute selected combined value for alert type dropdown
  const getAlertFormCombinedValue = (): string => {
    if (alertForm.alert_type === 'period_high') {
      if (alertForm.period === '26w') return 'period_high_26';
      if (alertForm.period === '13w') return 'period_high_13';
      return 'period_high';
    }
    if (alertForm.alert_type === 'period_low') {
      if (alertForm.period === '26w') return 'period_low_26';
      if (alertForm.period === '13w') return 'period_low_13';
      return 'period_low';
    }
    return alertForm.alert_type;
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
                  yahoo_ticker: stockDetail?.info?.yahoo_ticker || '',
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
            <div>
              <label htmlFor="yahoo_ticker" className="block text-sm font-medium mb-1">
                Yahoo Ticker
              </label>
              <input
                type="text"
                id="yahoo_ticker"
                value={stockSettingsForm.yahoo_ticker}
                onChange={(e) => setStockSettingsForm({ ...stockSettingsForm, yahoo_ticker: e.target.value })}
                className="w-full max-w-xs px-3 py-2 rounded-md border bg-background"
                placeholder="bijv. ENGI.PA"
              />
            </div>
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
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">
                Yahoo Ticker: <strong>{stockDetail?.info?.yahoo_ticker || '—'}</strong>
              </span>
            </div>
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

      {/* StockTwits Sentiment */}
      {stockDetail?.sentiment && (
        <div className="bg-card rounded-lg border">
          <div className="p-6 border-b">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Marktsentiment
            </h3>
          </div>
          <div className="p-6">
            <div className="space-y-4">
              {/* Sentiment bar */}
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-green-500 font-medium">
                    Bullish {stockDetail.sentiment.bullish_percent}%
                  </span>
                  <span className="text-red-500 font-medium">
                    Bearish {(100 - stockDetail.sentiment.bullish_percent).toFixed(1)}%
                  </span>
                </div>
                <div className="h-3 rounded-full bg-red-500/20 overflow-hidden">
                  <div
                    className="h-full bg-green-500 rounded-full transition-all"
                    style={{ width: `${stockDetail.sentiment.bullish_percent}%` }}
                  />
                </div>
              </div>

              {/* Stats */}
              <div className="flex items-center gap-6 text-sm text-muted-foreground">
                <span>{stockDetail.sentiment.bullish} bullish</span>
                <span>{stockDetail.sentiment.bearish} bearish</span>
                <span>van {stockDetail.sentiment.message_count} berichten</span>
              </div>

              <div className="text-xs text-muted-foreground">
                Bron: StockTwits
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Price Alerts */}
      <div className="bg-card rounded-lg border">
        <div className="p-6 border-b flex justify-between items-center">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Prijsalerts
          </h3>
          <button
            onClick={() => {
              setShowAlertForm(!showAlertForm);
              setAlertForm({ alert_type: 'period_high', period: '52w', threshold_price: '' });
            }}
            className="flex items-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" /> Toevoegen
          </button>
        </div>

        {showAlertForm && (
          <form onSubmit={handleCreateAlert} className="p-6 border-b bg-muted/50 space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium mb-1">Alert type</label>
                <select
                  value={getAlertFormCombinedValue()}
                  onChange={(e) => handleAlertTypeChange(e.target.value)}
                  className="w-full px-3 py-2 rounded-md border bg-background"
                >
                  {alertTypeOptions.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
              {['above', 'below'].includes(alertForm.alert_type) && (
                <div>
                  <label className="block text-xs font-medium mb-1">Drempelprijs</label>
                  <input
                    type="number"
                    step="0.01"
                    value={alertForm.threshold_price}
                    onChange={(e) => setAlertForm({ ...alertForm, threshold_price: e.target.value })}
                    className="w-full px-3 py-2 rounded-md border bg-background"
                    placeholder="0.00"
                    required
                  />
                </div>
              )}
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={createAlertMutation.isPending}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
              >
                {createAlertMutation.isPending ? 'Opslaan...' : 'Opslaan'}
              </button>
              <button
                type="button"
                onClick={() => setShowAlertForm(false)}
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
                <th className="text-left p-4 font-medium">Alert</th>
                <th className="text-center p-4 font-medium">Actief</th>
                <th className="text-left p-4 font-medium">Laatst getriggerd</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody>
              {stockAlerts?.map((alert) => (
                <tr key={alert.id} className="border-b hover:bg-muted/50">
                  <td className="p-4 font-medium">
                    {getAlertDescription(alert)}
                  </td>
                  <td className="p-4 text-center">
                    <button
                      onClick={() => handleToggleAlert(alert)}
                      disabled={updateAlertMutation.isPending}
                      className="text-muted-foreground hover:text-foreground transition-colors"
                      title={alert.enabled ? 'Uitschakelen' : 'Inschakelen'}
                    >
                      {alert.enabled ? (
                        <ToggleRight className="h-6 w-6 text-green-500" />
                      ) : (
                        <ToggleLeft className="h-6 w-6 text-muted-foreground" />
                      )}
                    </button>
                  </td>
                  <td className="p-4 text-muted-foreground text-sm">
                    {alert.last_triggered_at
                      ? new Date(alert.last_triggered_at).toLocaleString('nl-BE')
                      : '—'}
                  </td>
                  <td className="p-4">
                    <button
                      onClick={() => ticker && deleteAlertMutation.mutate({ alertId: alert.id, ticker })}
                      className="text-destructive hover:text-destructive/80"
                      title="Verwijderen"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
              {(!stockAlerts || stockAlerts.length === 0) && (
                <tr>
                  <td colSpan={4} className="p-4 text-center text-muted-foreground">
                    Geen prijsalerts ingesteld
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
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

      {/* Upcoming Ex-Dividend Dates */}
      {stockDetail?.upcoming_dividends && stockDetail.upcoming_dividends.length > 0 && (
        <div className="bg-card rounded-lg border">
          <div className="p-6 border-b">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              Aankomende Ex-Dividend Datums
            </h3>
          </div>
          <div className="p-6">
            <div className="flex flex-wrap gap-3">
              {stockDetail.upcoming_dividends.map((ud: { ex_date: string; estimated_per_share: number; currency: string; frequency: string }, idx: number) => (
                <div key={idx} className="flex items-center gap-3 px-4 py-3 bg-muted/50 rounded-lg border">
                  <div>
                    <div className="font-medium">{formatDate(ud.ex_date)}</div>
                    <div className="text-xs text-muted-foreground">{ud.frequency}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-medium text-green-600 dark:text-green-400">
                      {getCurrencySymbol(ud.currency)}{ud.estimated_per_share.toFixed(4)}
                    </div>
                    <div className="text-xs text-muted-foreground">per aandeel</div>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-muted-foreground mt-3">
              Geschatte datums en bedragen op basis van historische dividendpatronen.
            </p>
          </div>
        </div>
      )}

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
                  onChange={(e) => setTxForm({ ...txForm, quantity: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 rounded-md border bg-background"
                  step="any"
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
              {transactions?.map((tx) => {
                const isEditing = (field: string) => inlineEdit?.txId === tx.id && inlineEdit?.field === field;
                const editableCell = (field: string, displayValue: React.ReactNode, align: string = 'left', inputType: string = 'text') => {
                  if (isEditing(field)) {
                    return (
                      <td className={`p-1 ${align === 'right' ? 'text-right' : ''}`}>
                        <input
                          type={inputType}
                          value={inlineEdit!.value}
                          onChange={(e) => setInlineEdit({ ...inlineEdit!, value: e.target.value })}
                          onKeyDown={handleInlineKeyDown}
                          onBlur={saveInlineEdit}
                          autoFocus
                          step={inputType === 'number' ? 'any' : undefined}
                          className={`w-full px-2 py-1 rounded border bg-background text-sm ${align === 'right' ? 'text-right' : ''}`}
                        />
                      </td>
                    );
                  }
                  return (
                    <td
                      className={`p-4 cursor-pointer hover:bg-primary/10 rounded ${align === 'right' ? 'text-right' : ''}`}
                      onClick={() => setInlineEdit({ txId: tx.id, field, value: String((tx as any)[field] ?? '') })}
                    >
                      {displayValue}
                    </td>
                  );
                };

                return (
                  <tr key={tx.id} className="border-b hover:bg-muted/50">
                    {editableCell('date', formatDate(tx.date), 'left', 'date')}
                    {isEditing('transaction_type') ? (
                      <td className="p-1">
                        <select
                          value={inlineEdit!.value}
                          onChange={(e) => {
                            setInlineEdit({ ...inlineEdit!, value: e.target.value });
                            // Auto-save on select change
                            const updated: Record<string, any> = { ...tx };
                            updated.transaction_type = e.target.value;
                            const { id, ...payload } = updated;
                            updateTransaction.mutateAsync({ id: tx.id, data: payload as any });
                            setInlineEdit(null);
                          }}
                          onBlur={() => setInlineEdit(null)}
                          autoFocus
                          className="w-full px-2 py-1 rounded border bg-background text-sm"
                        >
                          <option value="BUY">Koop</option>
                          <option value="SELL">Verkoop</option>
                        </select>
                      </td>
                    ) : (
                      <td
                        className="p-4 cursor-pointer hover:bg-primary/10 rounded"
                        onClick={() => setInlineEdit({ txId: tx.id, field: 'transaction_type', value: tx.transaction_type })}
                      >
                        <span className={tx.transaction_type === 'BUY' ? 'text-green-500' : 'text-red-500'}>
                          {tx.transaction_type === 'BUY' ? 'Koop' : 'Verkoop'}
                        </span>
                      </td>
                    )}
                    {editableCell('quantity', tx.quantity, 'right', 'number')}
                    {editableCell('price_per_share', formatCurrency(tx.price_per_share, tx.currency), 'right', 'number')}
                    <td className="text-right p-4 text-muted-foreground">{formatCurrency(tx.quantity * tx.price_per_share, tx.currency)}</td>
                    {editableCell('fees', formatCurrency(tx.fees, 'EUR'), 'right', 'number')}
                    {editableCell('taxes', formatCurrency(tx.taxes, 'EUR'), 'right', 'number')}
                    {isEditing('broker') ? (
                      <td className="p-1">
                        <select
                          value={inlineEdit!.value}
                          onChange={(e) => {
                            const updated: Record<string, any> = { ...tx };
                            updated.broker = e.target.value;
                            const { id, ...payload } = updated;
                            updateTransaction.mutateAsync({ id: tx.id, data: payload as any });
                            setInlineEdit(null);
                          }}
                          onBlur={() => setInlineEdit(null)}
                          autoFocus
                          className="w-full px-2 py-1 rounded border bg-background text-sm"
                        >
                          {brokers?.map((b) => (
                            <option key={b} value={b}>{b}</option>
                          ))}
                        </select>
                      </td>
                    ) : (
                      <td
                        className="p-4 cursor-pointer hover:bg-primary/10 rounded"
                        onClick={() => setInlineEdit({ txId: tx.id, field: 'broker', value: tx.broker })}
                      >
                        {tx.broker}
                      </td>
                    )}
                    <td className="p-4">
                      <div className="flex gap-2">
                        <button
                          onClick={() => startEditTransaction(tx)}
                          className="text-muted-foreground hover:text-foreground"
                          title="Alles bewerken"
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
                );
              })}
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
