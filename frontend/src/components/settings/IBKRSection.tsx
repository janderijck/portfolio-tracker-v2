import { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getIBKRConfig, saveIBKRConfig, testIBKRConnection, syncIBKR, disconnectIBKR, getIBKRStatus } from '@/api/client';
import type { IBKRConfig, IBKRSyncResult } from '@/types';
import { Save, Check, Eye, EyeOff, TestTube2, RefreshCw, Link2, Unlink, LogOut } from 'lucide-react';

export default function IBKRSection() {
  const queryClient = useQueryClient();

  const [ibkrConfig, setIbkrConfig] = useState<IBKRConfig>({ flex_token: '', query_id: '' });
  const [showIbkrToken, setShowIbkrToken] = useState(false);
  const [ibkrConfigSaved, setIbkrConfigSaved] = useState(false);
  const [isSavingIbkrConfig, setIsSavingIbkrConfig] = useState(false);
  const [ibkrMessage, setIbkrMessage] = useState<{ success: boolean; message: string } | null>(null);
  const [isIbkrTesting, setIsIbkrTesting] = useState(false);
  const [isIbkrSyncing, setIsIbkrSyncing] = useState(false);
  const [ibkrSyncResult, setIbkrSyncResult] = useState<IBKRSyncResult | null>(null);
  const [isIbkrDisconnecting, setIsIbkrDisconnecting] = useState(false);

  const { data: ibkrStatus } = useQuery({
    queryKey: ['ibkr-status'],
    queryFn: getIBKRStatus,
  });

  const { data: ibkrConfigData } = useQuery({
    queryKey: ['ibkr-config'],
    queryFn: getIBKRConfig,
  });

  useEffect(() => {
    if (ibkrConfigData) {
      setIbkrConfig(ibkrConfigData);
    }
  }, [ibkrConfigData]);

  const handleSaveIbkrConfig = async () => {
    setIsSavingIbkrConfig(true);
    setIbkrMessage(null);
    try {
      await saveIBKRConfig(ibkrConfig);
      queryClient.invalidateQueries({ queryKey: ['ibkr-config'] });
      queryClient.invalidateQueries({ queryKey: ['ibkr-status'] });
      setIbkrConfigSaved(true);
      setTimeout(() => setIbkrConfigSaved(false), 2000);
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'Opslaan mislukt';
      setIbkrMessage({ success: false, message: errorMessage });
    } finally {
      setIsSavingIbkrConfig(false);
    }
  };

  const handleIbkrTest = async () => {
    setIsIbkrTesting(true);
    setIbkrMessage(null);
    try {
      const result = await testIBKRConnection();
      setIbkrMessage({ success: true, message: `${result.message} Account: ${result.account?.account_id || 'onbekend'}, ${result.account?.trades || 0} trades, ${result.account?.open_positions || 0} posities` });
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'Verbindingstest mislukt';
      setIbkrMessage({ success: false, message: errorMessage });
    } finally {
      setIsIbkrTesting(false);
    }
  };

  const handleIbkrSync = async () => {
    setIsIbkrSyncing(true);
    setIbkrMessage(null);
    setIbkrSyncResult(null);
    try {
      const result = await syncIBKR();
      setIbkrSyncResult(result);
      queryClient.invalidateQueries({ queryKey: ['ibkr-status'] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['dividends'] });
      queryClient.invalidateQueries({ queryKey: ['stocks'] });
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'Synchronisatie mislukt';
      setIbkrMessage({ success: false, message: errorMessage });
    } finally {
      setIsIbkrSyncing(false);
    }
  };

  const handleIbkrDisconnect = async () => {
    setIsIbkrDisconnecting(true);
    setIbkrMessage(null);
    setIbkrSyncResult(null);
    try {
      await disconnectIBKR();
      setIbkrConfig({ flex_token: '', query_id: '' });
      setIbkrMessage({ success: true, message: 'IBKR ontkoppeld' });
      queryClient.invalidateQueries({ queryKey: ['ibkr-status'] });
      queryClient.invalidateQueries({ queryKey: ['ibkr-config'] });
      setTimeout(() => setIbkrMessage(null), 3000);
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'Ontkoppelen mislukt';
      setIbkrMessage({ success: false, message: errorMessage });
    } finally {
      setIsIbkrDisconnecting(false);
    }
  };

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {ibkrStatus?.configured ? (
            <Link2 className="h-5 w-5 text-green-500" />
          ) : (
            <Unlink className="h-5 w-5 text-muted-foreground" />
          )}
          <h2 className="text-xl font-semibold">IBKR Flex Query Koppeling</h2>
        </div>
        {ibkrStatus?.configured && (
          <span className="text-xs px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded-full">
            Geconfigureerd
          </span>
        )}
      </div>

      <div className="space-y-4">
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Flex Token</label>
            <div className="relative">
              <input
                type={showIbkrToken ? "text" : "password"}
                value={ibkrConfig.flex_token}
                onChange={(e) => setIbkrConfig(prev => ({ ...prev, flex_token: e.target.value }))}
                placeholder="Flex Web Service Token..."
                className="w-full px-3 py-2 pr-10 border rounded-md bg-background text-sm"
              />
              <button
                type="button"
                onClick={() => setShowIbkrToken(!showIbkrToken)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showIbkrToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Query ID</label>
            <input
              type="text"
              value={ibkrConfig.query_id}
              onChange={(e) => setIbkrConfig(prev => ({ ...prev, query_id: e.target.value }))}
              placeholder="Flex Query ID (numeriek)..."
              className="w-full px-3 py-2 border rounded-md bg-background text-sm"
            />
          </div>
          <button
            onClick={handleSaveIbkrConfig}
            disabled={isSavingIbkrConfig || !ibkrConfig.flex_token || !ibkrConfig.query_id}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50 text-sm"
          >
            {ibkrConfigSaved ? (
              <>
                <Check className="h-4 w-4" />
                Opgeslagen
              </>
            ) : (
              <>
                <Save className="h-4 w-4" />
                Opslaan
              </>
            )}
          </button>
        </div>

        <hr className="border-border" />

        {ibkrMessage && (
          <div className={`p-3 rounded-md text-sm ${
            ibkrMessage.success
              ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-200'
              : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-200'
          }`}>
            {ibkrMessage.message}
          </div>
        )}

        <div className="flex items-center gap-3 flex-wrap">
          <button
            type="button"
            onClick={handleIbkrTest}
            disabled={isIbkrTesting || !ibkrStatus?.configured}
            className="flex items-center gap-2 px-4 py-2 border rounded-md hover:bg-accent transition-colors disabled:opacity-50 text-sm"
            title="Verbinding testen"
          >
            <TestTube2 className={`h-4 w-4 ${isIbkrTesting ? 'animate-pulse' : ''}`} />
            Verbinding testen
          </button>
          <button
            type="button"
            onClick={handleIbkrSync}
            disabled={isIbkrSyncing || !ibkrStatus?.configured}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50 text-sm"
            title="Synchroniseer transacties, dividenden en cash"
          >
            <RefreshCw className={`h-4 w-4 ${isIbkrSyncing ? 'animate-spin' : ''}`} />
            Synchroniseer
          </button>
          {ibkrStatus?.configured && (
            <button
              type="button"
              onClick={handleIbkrDisconnect}
              disabled={isIbkrDisconnecting}
              className="flex items-center gap-2 px-4 py-2 border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50 text-sm"
              title="IBKR ontkoppelen"
            >
              <LogOut className={`h-4 w-4 ${isIbkrDisconnecting ? 'animate-pulse' : ''}`} />
              Ontkoppel
            </button>
          )}
        </div>

        {ibkrSyncResult && (
          <div className="p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-md text-sm text-blue-800 dark:text-blue-200">
            <p className="font-medium mb-1">Synchronisatie voltooid</p>
            <ul className="space-y-0.5">
              {ibkrSyncResult.positions_found > 0 && (
                <li>{ibkrSyncResult.positions_found} open posities gevonden</li>
              )}
              {ibkrSyncResult.stocks_created > 0 && (
                <li>{ibkrSyncResult.stocks_created} nieuwe effecten aangemaakt</li>
              )}
              <li>{ibkrSyncResult.transactions_imported} transacties geimporteerd</li>
              <li>{ibkrSyncResult.dividends_imported} dividenden geimporteerd</li>
              <li>{ibkrSyncResult.cash_imported} kasbewegingen geimporteerd</li>
            </ul>
            {ibkrSyncResult.warnings.length > 0 && (
              <div className="mt-2 pt-2 border-t border-blue-200 dark:border-blue-700">
                <p className="font-medium mb-0.5">Waarschuwingen</p>
                <ul className="space-y-0.5 text-amber-700 dark:text-amber-300">
                  {ibkrSyncResult.warnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              </div>
            )}
            {ibkrSyncResult.errors.length > 0 && (
              <div className="mt-2 pt-2 border-t border-blue-200 dark:border-blue-700">
                <p className="font-medium mb-0.5">Fouten</p>
                <ul className="space-y-0.5 text-red-700 dark:text-red-300">
                  {ibkrSyncResult.errors.map((e, i) => <li key={i}>{e}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}

        {ibkrStatus?.last_sync && (
          <p className="text-xs text-muted-foreground">
            Laatste sync: {new Date(ibkrStatus.last_sync).toLocaleString('nl-BE')}
          </p>
        )}

        <div className="p-3 bg-muted/30 rounded-md">
          <p className="text-xs text-muted-foreground">
            <strong>Flex Query instellen in IBKR Client Portal:</strong>
            <br />1. Ga naar Performance & Reports &gt; Flex Queries
            <br />2. Maak een Activity Flex Query aan
            <br />3. Selecteer secties: Trades, Cash Transactions, Open Positions
            <br />4. Zorg dat ISIN veld is ingeschakeld bij elke sectie
            <br />5. Datumformaat: yyyy-MM-dd (ISO) of standaard yyyyMMdd
            <br />6. Kopieer de Flex Web Service Token en Query ID hierboven
          </p>
        </div>
      </div>
    </div>
  );
}
