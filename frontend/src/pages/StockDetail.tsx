import { useParams } from 'react-router-dom';
import { useTransactions, useDividends, useCreateTransaction, useDeleteTransaction, useCreateDividend, useDeleteDividend } from '@/hooks/usePortfolio';
import { useState } from 'react';
import { Loader2, Plus, Trash2 } from 'lucide-react';

export default function StockDetail() {
  const { ticker } = useParams<{ ticker: string }>();
  const { data: transactions, isLoading: loadingTx } = useTransactions(ticker);
  const { data: dividends, isLoading: loadingDiv } = useDividends(ticker);
  const createTransaction = useCreateTransaction();
  const deleteTransaction = useDeleteTransaction();
  const createDividend = useCreateDividend();
  const deleteDividend = useDeleteDividend();

  const [showTxForm, setShowTxForm] = useState(false);
  const [showDivForm, setShowDivForm] = useState(false);

  const [txForm, setTxForm] = useState({
    ticker: ticker || '',
    isin: '',
    name: '',
    broker: 'IBKR',
    date: new Date().toISOString().split('T')[0],
    type: 'buy' as 'buy' | 'sell',
    quantity: 0,
    price: 0,
    currency: 'EUR',
    exchange_rate: 1.0,
    fees: 0,
  });

  const [divForm, setDivForm] = useState({
    ticker: ticker || '',
    ex_date: new Date().toISOString().split('T')[0],
    pay_date: new Date().toISOString().split('T')[0],
    amount_gross: 0,
    tax_us: 0,
    tax_be: 0,
    amount_net: 0,
    currency: 'USD',
    received: false,
    tax_paid: false,
  });

  const formatCurrency = (value: number, currency: string = 'EUR') => {
    const symbol = currency === 'USD' ? '$' : '€';
    return `${symbol}${value.toLocaleString('nl-NL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const handleCreateTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    await createTransaction.mutateAsync(txForm);
    setShowTxForm(false);
  };

  const handleCreateDividend = async (e: React.FormEvent) => {
    e.preventDefault();
    await createDividend.mutateAsync(divForm);
    setShowDivForm(false);
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

      {/* Transactions */}
      <div className="bg-card rounded-lg border">
        <div className="p-6 border-b flex justify-between items-center">
          <h3 className="text-lg font-semibold">Transacties</h3>
          <button
            onClick={() => setShowTxForm(!showTxForm)}
            className="flex items-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" /> Toevoegen
          </button>
        </div>

        {showTxForm && (
          <form onSubmit={handleCreateTransaction} className="p-6 border-b bg-muted/50 space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <input
                type="date"
                value={txForm.date}
                onChange={(e) => setTxForm({ ...txForm, date: e.target.value })}
                className="px-3 py-2 rounded-md border bg-background"
              />
              <select
                value={txForm.type}
                onChange={(e) => setTxForm({ ...txForm, type: e.target.value as 'buy' | 'sell' })}
                className="px-3 py-2 rounded-md border bg-background"
              >
                <option value="buy">Koop</option>
                <option value="sell">Verkoop</option>
              </select>
              <input
                type="number"
                placeholder="Aantal"
                value={txForm.quantity || ''}
                onChange={(e) => setTxForm({ ...txForm, quantity: parseInt(e.target.value) || 0 })}
                className="px-3 py-2 rounded-md border bg-background"
              />
              <input
                type="number"
                step="0.01"
                placeholder="Prijs"
                value={txForm.price || ''}
                onChange={(e) => setTxForm({ ...txForm, price: parseFloat(e.target.value) || 0 })}
                className="px-3 py-2 rounded-md border bg-background"
              />
              <select
                value={txForm.broker}
                onChange={(e) => setTxForm({ ...txForm, broker: e.target.value })}
                className="px-3 py-2 rounded-md border bg-background"
              >
                <option value="IBKR">IBKR</option>
                <option value="DeGiro">DeGiro</option>
              </select>
              <select
                value={txForm.currency}
                onChange={(e) => setTxForm({ ...txForm, currency: e.target.value })}
                className="px-3 py-2 rounded-md border bg-background"
              >
                <option value="EUR">EUR</option>
                <option value="USD">USD</option>
              </select>
              <input
                type="number"
                step="0.0001"
                placeholder="Wisselkoers"
                value={txForm.exchange_rate || ''}
                onChange={(e) => setTxForm({ ...txForm, exchange_rate: parseFloat(e.target.value) || 1 })}
                className="px-3 py-2 rounded-md border bg-background"
              />
              <input
                type="number"
                step="0.01"
                placeholder="Kosten"
                value={txForm.fees || ''}
                onChange={(e) => setTxForm({ ...txForm, fees: parseFloat(e.target.value) || 0 })}
                className="px-3 py-2 rounded-md border bg-background"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              Opslaan
            </button>
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
                <th className="text-left p-4 font-medium">Broker</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody>
              {transactions?.map((tx) => (
                <tr key={tx.id} className="border-b hover:bg-muted/50">
                  <td className="p-4">{tx.date}</td>
                  <td className="p-4">
                    <span className={tx.type === 'buy' ? 'text-green-500' : 'text-red-500'}>
                      {tx.type === 'buy' ? 'Koop' : 'Verkoop'}
                    </span>
                  </td>
                  <td className="text-right p-4">{tx.quantity}</td>
                  <td className="text-right p-4">{formatCurrency(tx.price, tx.currency)}</td>
                  <td className="text-right p-4">{formatCurrency(tx.quantity * tx.price, tx.currency)}</td>
                  <td className="text-right p-4">{formatCurrency(tx.fees, tx.currency)}</td>
                  <td className="p-4">{tx.broker}</td>
                  <td className="p-4">
                    <button
                      onClick={() => deleteTransaction.mutate(tx.id)}
                      className="text-destructive hover:text-destructive/80"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
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
          <button
            onClick={() => setShowDivForm(!showDivForm)}
            className="flex items-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" /> Toevoegen
          </button>
        </div>

        {showDivForm && (
          <form onSubmit={handleCreateDividend} className="p-6 border-b bg-muted/50 space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <input
                type="date"
                placeholder="Ex-date"
                value={divForm.ex_date}
                onChange={(e) => setDivForm({ ...divForm, ex_date: e.target.value })}
                className="px-3 py-2 rounded-md border bg-background"
              />
              <input
                type="date"
                placeholder="Pay-date"
                value={divForm.pay_date}
                onChange={(e) => setDivForm({ ...divForm, pay_date: e.target.value })}
                className="px-3 py-2 rounded-md border bg-background"
              />
              <input
                type="number"
                step="0.01"
                placeholder="Bruto"
                value={divForm.amount_gross || ''}
                onChange={(e) => setDivForm({ ...divForm, amount_gross: parseFloat(e.target.value) || 0 })}
                className="px-3 py-2 rounded-md border bg-background"
              />
              <input
                type="number"
                step="0.01"
                placeholder="US Tax"
                value={divForm.tax_us || ''}
                onChange={(e) => setDivForm({ ...divForm, tax_us: parseFloat(e.target.value) || 0 })}
                className="px-3 py-2 rounded-md border bg-background"
              />
              <input
                type="number"
                step="0.01"
                placeholder="BE Tax"
                value={divForm.tax_be || ''}
                onChange={(e) => setDivForm({ ...divForm, tax_be: parseFloat(e.target.value) || 0 })}
                className="px-3 py-2 rounded-md border bg-background"
              />
              <input
                type="number"
                step="0.01"
                placeholder="Netto"
                value={divForm.amount_net || ''}
                onChange={(e) => setDivForm({ ...divForm, amount_net: parseFloat(e.target.value) || 0 })}
                className="px-3 py-2 rounded-md border bg-background"
              />
              <select
                value={divForm.currency}
                onChange={(e) => setDivForm({ ...divForm, currency: e.target.value })}
                className="px-3 py-2 rounded-md border bg-background"
              >
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
              </select>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={divForm.received}
                  onChange={(e) => setDivForm({ ...divForm, received: e.target.checked })}
                />
                Ontvangen
              </label>
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              Opslaan
            </button>
          </form>
        )}

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="text-left p-4 font-medium">Ex-date</th>
                <th className="text-left p-4 font-medium">Pay-date</th>
                <th className="text-right p-4 font-medium">Bruto</th>
                <th className="text-right p-4 font-medium">US Tax</th>
                <th className="text-right p-4 font-medium">BE Tax</th>
                <th className="text-right p-4 font-medium">Netto</th>
                <th className="text-center p-4 font-medium">Ontvangen</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody>
              {dividends?.map((div) => (
                <tr key={div.id} className="border-b hover:bg-muted/50">
                  <td className="p-4">{div.ex_date}</td>
                  <td className="p-4">{div.pay_date}</td>
                  <td className="text-right p-4">{formatCurrency(div.amount_gross, div.currency)}</td>
                  <td className="text-right p-4">{formatCurrency(div.tax_us, div.currency)}</td>
                  <td className="text-right p-4">{formatCurrency(div.tax_be, 'EUR')}</td>
                  <td className="text-right p-4">{formatCurrency(div.amount_net, div.currency)}</td>
                  <td className="text-center p-4">{div.received ? '✓' : '—'}</td>
                  <td className="p-4">
                    <button
                      onClick={() => deleteDividend.mutate(div.id)}
                      className="text-destructive hover:text-destructive/80"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
