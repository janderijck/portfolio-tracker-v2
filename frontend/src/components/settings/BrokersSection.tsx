import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { createBroker, getBrokerDetails, updateBrokerCash, updateBrokerAccountType } from '@/api/client';
import { Save, Check, Plus, X, Building2 } from 'lucide-react';

export default function BrokersSection() {
  const queryClient = useQueryClient();

  const [newBroker, setNewBroker] = useState('');
  const [cashEdits, setCashEdits] = useState<Record<string, { currency: string; balance: string }[]>>({});
  const [cashSaved, setCashSaved] = useState<Record<string, boolean>>({});
  const [accountTypeSaved, setAccountTypeSaved] = useState<Record<string, boolean>>({});

  const { data: brokerDetails } = useQuery({
    queryKey: ['brokers', 'details'],
    queryFn: getBrokerDetails,
  });

  const brokerMutation = useMutation({
    mutationFn: createBroker,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['brokers'] });
      setNewBroker('');
    },
  });

  useEffect(() => {
    if (brokerDetails) {
      const edits: Record<string, { currency: string; balance: string }[]> = {};
      for (const b of brokerDetails) {
        edits[b.broker_name] = b.cash_balances.length > 0
          ? b.cash_balances.map(cb => ({ currency: cb.currency, balance: cb.balance.toString() }))
          : [{ currency: 'EUR', balance: '0' }];
      }
      setCashEdits(edits);
    }
  }, [brokerDetails]);

  const handleSaveCash = async (brokerName: string, index: number) => {
    const rows = cashEdits[brokerName];
    if (!rows || !rows[index]) return;
    const row = rows[index];
    const key = `${brokerName}-${index}`;
    try {
      await updateBrokerCash(brokerName, {
        currency: row.currency,
        balance: parseFloat(row.balance) || 0,
      });
      queryClient.invalidateQueries({ queryKey: ['brokers'] });
      queryClient.invalidateQueries({ queryKey: ['cashSummary'] });
      setCashSaved(prev => ({ ...prev, [key]: true }));
      setTimeout(() => setCashSaved(prev => ({ ...prev, [key]: false })), 2000);
    } catch (error) {
      console.error('Failed to save cash:', error);
    }
  };

  const handleAddCurrencyRow = (brokerName: string) => {
    setCashEdits(prev => ({
      ...prev,
      [brokerName]: [...(prev[brokerName] || []), { currency: 'USD', balance: '0' }],
    }));
  };

  const handleRemoveCurrencyRow = async (brokerName: string, index: number) => {
    const rows = cashEdits[brokerName];
    if (!rows || rows.length <= 1) return;
    const removed = rows[index];
    // Set balance to 0 on server to delete the row
    try {
      await updateBrokerCash(brokerName, { currency: removed.currency, balance: 0 });
      setCashEdits(prev => ({
        ...prev,
        [brokerName]: prev[brokerName].filter((_, i) => i !== index),
      }));
      queryClient.invalidateQueries({ queryKey: ['brokers'] });
      queryClient.invalidateQueries({ queryKey: ['cashSummary'] });
    } catch (error) {
      console.error('Failed to remove currency row:', error);
    }
  };

  const handleAccountTypeChange = async (brokerName: string, accountType: string) => {
    try {
      await updateBrokerAccountType(brokerName, accountType);
      queryClient.invalidateQueries({ queryKey: ['brokers'] });
      setAccountTypeSaved(prev => ({ ...prev, [brokerName]: true }));
      setTimeout(() => setAccountTypeSaved(prev => ({ ...prev, [brokerName]: false })), 2000);
    } catch (error) {
      console.error('Failed to save account type:', error);
    }
  };

  const handleAddBroker = (e: React.FormEvent) => {
    e.preventDefault();
    if (newBroker.trim()) {
      brokerMutation.mutate(newBroker.trim());
    }
  };

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center gap-2 mb-4">
        <Building2 className="h-5 w-5 text-primary" />
        <h2 className="text-xl font-semibold">Brokers</h2>
      </div>

      <div className="space-y-4">
        {brokerDetails && brokerDetails.length > 0 ? (
          <div className="overflow-x-auto border border-border rounded-md">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Broker</th>
                  <th className="px-3 py-2 text-left font-medium">Account</th>
                  <th className="px-3 py-2 text-left font-medium">Cash Saldo</th>
                  <th className="px-3 py-2 text-left font-medium">Valuta</th>
                  <th className="px-3 py-2 text-left font-medium">Actie</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {brokerDetails.map((broker) => {
                  const rows = cashEdits[broker.broker_name] || [{ currency: 'EUR', balance: '0' }];
                  return rows.map((row, idx) => (
                    <tr key={`${broker.broker_name}-${idx}`} className="hover:bg-muted/30">
                      <td className="px-3 py-2 font-medium">
                        {idx === 0 ? broker.broker_name : ''}
                      </td>
                      <td className="px-3 py-2">
                        {idx === 0 ? (
                          <div className="flex items-center gap-1">
                            <select
                              value={broker.account_type || 'Priv\u00e9'}
                              onChange={(e) => handleAccountTypeChange(broker.broker_name, e.target.value)}
                              className="px-2 py-1 border rounded-md bg-background text-sm"
                            >
                              <option value="Priv\u00e9">Priv\u00e9</option>
                              <option value="TechVibe">TechVibe</option>
                            </select>
                            {accountTypeSaved[broker.broker_name] && (
                              <Check className="h-3 w-3 text-green-500" />
                            )}
                          </div>
                        ) : null}
                      </td>
                      <td className="px-3 py-2">
                        <input
                          type="number"
                          step="0.01"
                          value={row.balance}
                          onChange={(e) => setCashEdits(prev => {
                            const updated = [...(prev[broker.broker_name] || [])];
                            updated[idx] = { ...updated[idx], balance: e.target.value };
                            return { ...prev, [broker.broker_name]: updated };
                          })}
                          className="w-32 px-2 py-1 border rounded-md bg-background text-right"
                        />
                      </td>
                      <td className="px-3 py-2">
                        <select
                          value={row.currency}
                          onChange={(e) => setCashEdits(prev => {
                            const updated = [...(prev[broker.broker_name] || [])];
                            updated[idx] = { ...updated[idx], currency: e.target.value };
                            return { ...prev, [broker.broker_name]: updated };
                          })}
                          className="px-2 py-1 border rounded-md bg-background"
                        >
                          <option value="EUR">EUR</option>
                          <option value="USD">USD</option>
                          <option value="GBP">GBP</option>
                          <option value="CHF">CHF</option>
                        </select>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleSaveCash(broker.broker_name, idx)}
                            className="flex items-center gap-1 px-3 py-1 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 text-xs"
                          >
                            {cashSaved[`${broker.broker_name}-${idx}`] ? (
                              <>
                                <Check className="h-3 w-3" />
                                Opgeslagen
                              </>
                            ) : (
                              <>
                                <Save className="h-3 w-3" />
                                Opslaan
                              </>
                            )}
                          </button>
                          <button
                            onClick={() => handleAddCurrencyRow(broker.broker_name)}
                            className="flex items-center gap-1 px-2 py-1 border rounded-md hover:bg-accent text-xs"
                            title="Valuta toevoegen"
                          >
                            <Plus className="h-3 w-3" />
                          </button>
                          {rows.length > 1 && (
                            <button
                              onClick={() => handleRemoveCurrencyRow(broker.broker_name, idx)}
                              className="flex items-center gap-1 px-2 py-1 border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 text-xs"
                              title="Valuta verwijderen"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ));
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-muted-foreground text-sm">Geen brokers geconfigureerd.</p>
        )}

        <form onSubmit={handleAddBroker} className="flex gap-2">
          <input
            type="text"
            value={newBroker}
            onChange={(e) => setNewBroker(e.target.value)}
            placeholder="Nieuwe broker naam..."
            className="flex-1 px-3 py-2 border rounded-md bg-background"
          />
          <button
            type="submit"
            disabled={!newBroker.trim() || brokerMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            Toevoegen
          </button>
        </form>
      </div>
    </div>
  );
}
