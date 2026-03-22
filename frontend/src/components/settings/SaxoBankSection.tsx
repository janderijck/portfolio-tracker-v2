import { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { syncSaxo, getSaxoStatus, getSaxoAuthUrl, disconnectSaxo, importSaxoPositions, getSaxoConfig, saveSaxoConfig } from '@/api/client';
import type { SaxoPosition, SaxoConfig, SaxoDividendSyncResult } from '@/types';
import { Save, Check, Eye, EyeOff, RefreshCw, Link2, Unlink, LogIn, LogOut, Download } from 'lucide-react';

export default function SaxoBankSection() {
  const queryClient = useQueryClient();

  const [saxoMessage, setSaxoMessage] = useState<{ success: boolean; message: string } | null>(null);
  const [isSaxoSyncing, setIsSaxoSyncing] = useState(false);
  const [saxoSyncResult, setSaxoSyncResult] = useState<{ matched: number; unmatched: number; missing_local: number; dividends?: SaxoDividendSyncResult | null } | null>(null);
  const [saxoUnmatchedPositions, setSaxoUnmatchedPositions] = useState<SaxoPosition[]>([]);
  const [selectedPositions, setSelectedPositions] = useState<Set<number>>(new Set());
  const [isImporting, setIsImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ imported_stocks: number; imported_transactions: number; skipped: number; errors: string[] } | null>(null);
  const [isSaxoConnecting, setIsSaxoConnecting] = useState(false);
  const [isSaxoDisconnecting, setIsSaxoDisconnecting] = useState(false);
  const [saxoConfig, setSaxoConfig] = useState<SaxoConfig>({ client_id: '', client_secret: '', redirect_uri: '', auth_url: '', token_url: '' });
  const [showSaxoSecret, setShowSaxoSecret] = useState(false);
  const [saxoConfigSaved, setSaxoConfigSaved] = useState(false);
  const [isSavingSaxoConfig, setIsSavingSaxoConfig] = useState(false);

  const { data: saxoStatus } = useQuery({
    queryKey: ['saxo-status'],
    queryFn: getSaxoStatus,
  });

  const { data: saxoConfigData } = useQuery({
    queryKey: ['saxo-config'],
    queryFn: getSaxoConfig,
  });

  useEffect(() => {
    if (saxoConfigData) {
      setSaxoConfig(saxoConfigData);
    }
  }, [saxoConfigData]);

  // Check for OAuth result from redirect
  useEffect(() => {
    const resultStr = localStorage.getItem('saxo_oauth_result');
    if (resultStr) {
      localStorage.removeItem('saxo_oauth_result');
      const result = JSON.parse(resultStr);
      setSaxoMessage(result);
      queryClient.invalidateQueries({ queryKey: ['saxo-status'] });
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      setTimeout(() => setSaxoMessage(null), 5000);
    }
  }, [queryClient]);

  const handleSaxoConnect = async () => {
    setIsSaxoConnecting(true);
    setSaxoMessage(null);
    try {
      const { url } = await getSaxoAuthUrl();
      window.location.href = url;
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'Kon OAuth URL niet ophalen';
      setSaxoMessage({ success: false, message: errorMessage });
      setIsSaxoConnecting(false);
    }
  };

  const handleSaxoDisconnect = async () => {
    setIsSaxoDisconnecting(true);
    setSaxoMessage(null);
    try {
      await disconnectSaxo();
      setSaxoMessage({ success: true, message: 'Saxo ontkoppeld' });
      queryClient.invalidateQueries({ queryKey: ['saxo-status'] });
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      setTimeout(() => setSaxoMessage(null), 3000);
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'Ontkoppelen mislukt';
      setSaxoMessage({ success: false, message: errorMessage });
    } finally {
      setIsSaxoDisconnecting(false);
    }
  };

  const handleSaveSaxoConfig = async () => {
    setIsSavingSaxoConfig(true);
    try {
      await saveSaxoConfig(saxoConfig);
      queryClient.invalidateQueries({ queryKey: ['saxo-config'] });
      queryClient.invalidateQueries({ queryKey: ['saxo-status'] });
      setSaxoConfigSaved(true);
      setTimeout(() => setSaxoConfigSaved(false), 2000);
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'Opslaan mislukt';
      setSaxoMessage({ success: false, message: errorMessage });
    } finally {
      setIsSavingSaxoConfig(false);
    }
  };

  const handleSaxoSync = async () => {
    setIsSaxoSyncing(true);
    setSaxoSyncResult(null);
    setSaxoUnmatchedPositions([]);
    setSelectedPositions(new Set());
    setImportResult(null);
    try {
      const result = await syncSaxo();
      setSaxoSyncResult({
        matched: result.matched,
        unmatched: result.unmatched,
        missing_local: result.missing_local,
        dividends: result.dividends,
      });

      // Store unmatched positions for import UI
      const unmatched = result.positions.filter(p => !p.matched_ticker);
      setSaxoUnmatchedPositions(unmatched);
      // Select all by default
      setSelectedPositions(new Set(unmatched.map(p => p.uic)));

      queryClient.invalidateQueries({ queryKey: ['saxo-status'] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['dividends'] });
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'Synchronisatie mislukt';
      setSaxoMessage({ success: false, message: errorMessage });
    } finally {
      setIsSaxoSyncing(false);
    }
  };

  const handleImportPositions = async () => {
    const toImport = saxoUnmatchedPositions.filter(p => selectedPositions.has(p.uic));
    if (toImport.length === 0) return;

    setIsImporting(true);
    setImportResult(null);
    try {
      const result = await importSaxoPositions({ positions: toImport });
      setImportResult(result);
      setSaxoUnmatchedPositions([]);
      setSelectedPositions(new Set());
      // Refresh data
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['saxo-status'] });
      queryClient.invalidateQueries({ queryKey: ['stocks'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'Import mislukt';
      setSaxoMessage({ success: false, message: errorMessage });
    } finally {
      setIsImporting(false);
    }
  };

  const togglePosition = (uic: number) => {
    setSelectedPositions(prev => {
      const next = new Set(prev);
      if (next.has(uic)) {
        next.delete(uic);
      } else {
        next.add(uic);
      }
      return next;
    });
  };

  const toggleAllPositions = () => {
    if (selectedPositions.size === saxoUnmatchedPositions.length) {
      setSelectedPositions(new Set());
    } else {
      setSelectedPositions(new Set(saxoUnmatchedPositions.map(p => p.uic)));
    }
  };

  const calculateBuyPrice = (pos: SaxoPosition): number => {
    if (pos.pnl != null && pos.quantity > 0) {
      return (pos.current_value - pos.pnl) / pos.quantity;
    }
    if (pos.pnl_percent != null && pos.pnl_percent !== 0) {
      return pos.current_price / (1 + pos.pnl_percent / 100);
    }
    return pos.current_price;
  };

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {saxoStatus?.connected ? (
            <Link2 className="h-5 w-5 text-green-500" />
          ) : (
            <Unlink className="h-5 w-5 text-muted-foreground" />
          )}
          <h2 className="text-xl font-semibold">Saxo Bank Koppeling</h2>
        </div>
        {saxoStatus?.connected && (
          <span className="text-xs px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded-full">
            Verbonden
          </span>
        )}
      </div>

      <div className="space-y-4">
        {/* Saxo API Configuration */}
        <div className="space-y-3">
          <h3 className="text-sm font-medium">API Configuratie</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-muted-foreground mb-1">App Key</label>
              <input
                type="text"
                value={saxoConfig.client_id}
                onChange={(e) => setSaxoConfig(prev => ({ ...prev, client_id: e.target.value }))}
                placeholder="Saxo App Key..."
                className="w-full px-3 py-2 border rounded-md bg-background text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">App Secret (optioneel)</label>
              <div className="relative">
                <input
                  type={showSaxoSecret ? "text" : "password"}
                  value={saxoConfig.client_secret}
                  onChange={(e) => setSaxoConfig(prev => ({ ...prev, client_secret: e.target.value }))}
                  placeholder="Saxo App Secret..."
                  className="w-full px-3 py-2 pr-10 border rounded-md bg-background text-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowSaxoSecret(!showSaxoSecret)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showSaxoSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Authorization Endpoint</label>
              <input
                type="text"
                value={saxoConfig.auth_url}
                onChange={(e) => setSaxoConfig(prev => ({ ...prev, auth_url: e.target.value }))}
                placeholder="https://live.logonvalidation.net/authorize"
                className="w-full px-3 py-2 border rounded-md bg-background text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Token Endpoint</label>
              <input
                type="text"
                value={saxoConfig.token_url}
                onChange={(e) => setSaxoConfig(prev => ({ ...prev, token_url: e.target.value }))}
                placeholder="https://live.logonvalidation.net/token"
                className="w-full px-3 py-2 border rounded-md bg-background text-sm"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs text-muted-foreground mb-1">Redirect URI</label>
              <input
                type="text"
                value={saxoConfig.redirect_uri}
                onChange={(e) => setSaxoConfig(prev => ({ ...prev, redirect_uri: e.target.value }))}
                placeholder="https://jouw-app.com/saxo-callback"
                className="w-full px-3 py-2 border rounded-md bg-background text-sm"
              />
            </div>
          </div>
          <button
            onClick={handleSaveSaxoConfig}
            disabled={isSavingSaxoConfig || !saxoConfig.client_id}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50 text-sm"
          >
            {saxoConfigSaved ? (
              <>
                <Check className="h-4 w-4" />
                Opgeslagen
              </>
            ) : (
              <>
                <Save className="h-4 w-4" />
                Config opslaan
              </>
            )}
          </button>
        </div>

        <hr className="border-border" />

        {saxoMessage && (
          <div className={`p-3 rounded-md text-sm ${
            saxoMessage.success
              ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-200'
              : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-200'
          }`}>
            {saxoMessage.message}
          </div>
        )}

        {!saxoStatus?.connected ? (
          <div>
            <p className="text-sm text-muted-foreground mb-4">
              Koppel je Saxo Bank account om posities en koersen automatisch te synchroniseren.
              Je wordt doorgestuurd naar de Saxo login pagina om toegang te verlenen.
            </p>
            <button
              onClick={handleSaxoConnect}
              disabled={isSaxoConnecting || !saxoConfig.client_id}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              <LogIn className={`h-4 w-4 ${isSaxoConnecting ? 'animate-pulse' : ''}`} />
              {isSaxoConnecting ? 'Doorsturen...' : 'Verbind met Saxo'}
            </button>
            {!saxoConfig.client_id && (
              <p className="text-xs text-muted-foreground mt-2">
                Vul eerst de API configuratie hierboven in om te kunnen verbinden.
              </p>
            )}
          </div>
        ) : (
          <>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleSaxoSync}
                disabled={isSaxoSyncing}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50"
                title="Synchroniseer posities en prijzen"
              >
                <RefreshCw className={`h-4 w-4 ${isSaxoSyncing ? 'animate-spin' : ''}`} />
                Synchroniseer
              </button>
              <button
                type="button"
                onClick={handleSaxoDisconnect}
                disabled={isSaxoDisconnecting}
                className="flex items-center gap-2 px-4 py-2 border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50"
                title="Saxo ontkoppelen"
              >
                <LogOut className={`h-4 w-4 ${isSaxoDisconnecting ? 'animate-pulse' : ''}`} />
                Ontkoppel
              </button>
            </div>

            {saxoSyncResult && (
              <div className="p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-md text-sm text-blue-800 dark:text-blue-200">
                <p className="font-medium mb-1">Synchronisatie voltooid</p>
                <ul className="space-y-0.5">
                  <li>{saxoSyncResult.matched} posities gekoppeld aan lokale effecten</li>
                  {saxoSyncResult.unmatched > 0 && (
                    <li>{saxoSyncResult.unmatched} posities alleen bij Saxo (niet lokaal gevonden)</li>
                  )}
                  {saxoSyncResult.missing_local > 0 && (
                    <li>{saxoSyncResult.missing_local} lokale Saxo-effecten niet meer bij Saxo</li>
                  )}
                </ul>
                {saxoSyncResult.dividends && (
                  <div className="mt-2 pt-2 border-t border-blue-200 dark:border-blue-700">
                    <p className="font-medium mb-0.5">Dividenden</p>
                    <ul className="space-y-0.5">
                      {saxoSyncResult.dividends.imported > 0 && (
                        <li>{saxoSyncResult.dividends.imported} nieuwe dividenden geimporteerd</li>
                      )}
                      {saxoSyncResult.dividends.skipped_duplicate > 0 && (
                        <li>{saxoSyncResult.dividends.skipped_duplicate} duplicaten overgeslagen</li>
                      )}
                      {saxoSyncResult.dividends.skipped_unmatched > 0 && (
                        <li>{saxoSyncResult.dividends.skipped_unmatched} dividenden overgeslagen (geen lokale match)</li>
                      )}
                      {saxoSyncResult.dividends.imported === 0 && saxoSyncResult.dividends.skipped_duplicate === 0 && saxoSyncResult.dividends.skipped_unmatched === 0 && (
                        <li>Geen nieuwe dividenden gevonden</li>
                      )}
                      {!saxoSyncResult.dividends.ca_endpoint_available && (
                        <li className="text-amber-700 dark:text-amber-300">CA endpoint niet beschikbaar, fallback gebruikt</li>
                      )}
                      {saxoSyncResult.dividends.errors.length > 0 && (
                        <li className="text-red-700 dark:text-red-300">
                          {saxoSyncResult.dividends.errors.length} fout(en): {saxoSyncResult.dividends.errors[0]}
                        </li>
                      )}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {importResult && (
              <div className={`p-3 rounded-md text-sm ${
                importResult.errors.length === 0
                  ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-200'
                  : 'bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-200'
              }`}>
                <p className="font-medium mb-1">Import voltooid</p>
                <p>{importResult.imported_stocks} effecten en {importResult.imported_transactions} transacties geimporteerd</p>
                {importResult.skipped > 0 && <p>{importResult.skipped} overgeslagen (bestaan al)</p>}
                {importResult.errors.length > 0 && (
                  <ul className="mt-1 space-y-0.5">
                    {importResult.errors.map((err, i) => <li key={i}>{err}</li>)}
                  </ul>
                )}
              </div>
            )}

            {saxoUnmatchedPositions.length > 0 && (
              <div className="space-y-3">
                <p className="text-sm font-medium">
                  Ongematchte posities ({saxoUnmatchedPositions.length}) - selecteer om te importeren:
                </p>
                <div className="overflow-x-auto border border-border rounded-md">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="px-3 py-2 text-left w-8">
                          <input
                            type="checkbox"
                            checked={selectedPositions.size === saxoUnmatchedPositions.length}
                            onChange={toggleAllPositions}
                            className="rounded"
                          />
                        </th>
                        <th className="px-3 py-2 text-left">Naam</th>
                        <th className="px-3 py-2 text-left">ISIN</th>
                        <th className="px-3 py-2 text-right">Aantal</th>
                        <th className="px-3 py-2 text-right">Aankoopprijs</th>
                        <th className="px-3 py-2 text-right">Huidige prijs</th>
                        <th className="px-3 py-2 text-right">W/V</th>
                        <th className="px-3 py-2 text-left">Valuta</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {saxoUnmatchedPositions.map(pos => {
                        const buyPrice = calculateBuyPrice(pos);
                        return (
                          <tr key={pos.uic} className="hover:bg-muted/30">
                            <td className="px-3 py-2">
                              <input
                                type="checkbox"
                                checked={selectedPositions.has(pos.uic)}
                                onChange={() => togglePosition(pos.uic)}
                                className="rounded"
                              />
                            </td>
                            <td className="px-3 py-2 font-medium">{pos.name}</td>
                            <td className="px-3 py-2 text-muted-foreground font-mono text-xs">{pos.isin || '-'}</td>
                            <td className="px-3 py-2 text-right">{pos.quantity}</td>
                            <td className="px-3 py-2 text-right">{buyPrice.toFixed(2)}</td>
                            <td className="px-3 py-2 text-right">{pos.current_price.toFixed(2)}</td>
                            <td className={`px-3 py-2 text-right ${
                              (pos.pnl_percent ?? 0) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                            }`}>
                              {pos.pnl_percent != null ? `${pos.pnl_percent >= 0 ? '+' : ''}${pos.pnl_percent.toFixed(2)}%` : '-'}
                            </td>
                            <td className="px-3 py-2">{pos.currency}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <button
                  onClick={handleImportPositions}
                  disabled={selectedPositions.size === 0 || isImporting}
                  className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  <Download className={`h-4 w-4 ${isImporting ? 'animate-pulse' : ''}`} />
                  {isImporting
                    ? 'Importeren...'
                    : `Importeer ${selectedPositions.size} positie${selectedPositions.size !== 1 ? 's' : ''}`
                  }
                </button>
              </div>
            )}

            {saxoStatus?.last_sync && (
              <p className="text-xs text-muted-foreground">
                Laatste sync: {new Date(saxoStatus.last_sync).toLocaleString('nl-BE')}
                {saxoStatus.cached_prices > 0 && ` (${saxoStatus.cached_prices} koersen gecacht)`}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
