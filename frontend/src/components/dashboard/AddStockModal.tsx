import { useState, useCallback, useRef } from 'react';
import { Loader2, X } from 'lucide-react';
import type { StockInfoCreate } from '@/types';
import { searchStocks } from '@/api/client';
import { useCreateStock, useCreateTransaction } from '@/hooks/usePortfolio';
import { getTodayISO, getCurrencySymbol } from '@/utils/formatting';
import DateInput from '@/components/DateInput';

interface AddStockModalProps {
  open: boolean;
  onClose: () => void;
  brokers: string[] | undefined;
}

export default function AddStockModal({ open, onClose, brokers }: AddStockModalProps) {
  const createStock = useCreateStock();
  const createTransaction = useCreateTransaction();

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

  const searchTimerRef = useRef<ReturnType<typeof setTimeout>>();

  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query);
    if (query.length < 2) {
      setSearchResults([]);
      setShowSearchResults(false);
      return;
    }

    clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(async () => {
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
    }, 300);
  }, []);

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

      onClose();
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

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto py-8">
      <div className="bg-card rounded-lg border p-6 w-full max-w-lg mx-4">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold">Aandeel Toevoegen</h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
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
                <option value="EUR">EUR (&euro;)</option>
                <option value="USD">USD ($)</option>
                <option value="GBP">GBP (&pound;)</option>
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
                <label className="block text-sm font-medium mb-1">Kosten (&euro;)</label>
                <input
                  type="number"
                  step="0.01"
                  value={transaction.fees || ''}
                  onChange={(e) => setTransaction({ ...transaction, fees: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Belasting (&euro;)</label>
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
              onClick={onClose}
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
  );
}
