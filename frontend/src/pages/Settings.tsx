import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSettings, updateSettings, createBroker, testFinnhubApi, resetDatabase, syncSaxo, getSaxoStatus, getSaxoAuthUrl, disconnectSaxo, importSaxoPositions, getSaxoConfig, saveSaxoConfig, getBrokerDetails, updateBrokerCash, updateBrokerAccountType, getIBKRConfig, saveIBKRConfig, testIBKRConnection, syncIBKR, disconnectIBKR, getIBKRStatus, getTelegramConfig, saveTelegramConfig, testTelegram, disconnectTelegram } from '@/api/client';
import type { SaxoPosition, SaxoConfig, SaxoDividendSyncResult, IBKRConfig, IBKRSyncResult, TelegramConfig } from '@/types';
import { saveDateFormat } from '@/utils/formatting';
import { Settings as SettingsIcon, Save, Check, Plus, X, Building2, Zap, Hand, Eye, EyeOff, TestTube2, Trash2, AlertTriangle, RefreshCw, Link2, Unlink, LogIn, LogOut, Download, Bell } from 'lucide-react';

const dateFormats = [
  { value: 'DD/MM/YYYY', label: 'DD/MM/YYYY (Europees)', example: '23/11/2025' },
  { value: 'MM/DD/YYYY', label: 'MM/DD/YYYY (Amerikaans)', example: '11/23/2025' },
  { value: 'YYYY-MM-DD', label: 'YYYY-MM-DD (ISO)', example: '2025-11-23' },
];

export default function Settings() {
  const queryClient = useQueryClient();
  const [dateFormat, setDateFormat] = useState('DD/MM/YYYY');
  const [finnhubApiKey, setFinnhubApiKey] = useState('');
  const [openfigiApiKey, setOpenfigiApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [showOpenfigiKey, setShowOpenfigiKey] = useState(false);
  const [saved, setSaved] = useState(false);
  const [newBroker, setNewBroker] = useState('');
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [resetConfirmText, setResetConfirmText] = useState('');
  const [resetSuccess, setResetSuccess] = useState(false);
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

  // IBKR state
  const [ibkrConfig, setIbkrConfig] = useState<IBKRConfig>({ flex_token: '', query_id: '' });
  const [showIbkrToken, setShowIbkrToken] = useState(false);
  const [ibkrConfigSaved, setIbkrConfigSaved] = useState(false);
  const [isSavingIbkrConfig, setIsSavingIbkrConfig] = useState(false);
  const [ibkrMessage, setIbkrMessage] = useState<{ success: boolean; message: string } | null>(null);
  const [isIbkrTesting, setIsIbkrTesting] = useState(false);
  const [isIbkrSyncing, setIsIbkrSyncing] = useState(false);
  const [ibkrSyncResult, setIbkrSyncResult] = useState<IBKRSyncResult | null>(null);
  const [isIbkrDisconnecting, setIsIbkrDisconnecting] = useState(false);

  // Telegram state
  const [telegramConfig, setTelegramConfig] = useState<TelegramConfig>({ bot_token: '', chat_id: '' });
  const [showTelegramToken, setShowTelegramToken] = useState(false);
  const [telegramConfigSaved, setTelegramConfigSaved] = useState(false);
  const [isSavingTelegramConfig, setIsSavingTelegramConfig] = useState(false);
  const [telegramMessage, setTelegramMessage] = useState<{ success: boolean; message: string } | null>(null);
  const [isTelegramTesting, setIsTelegramTesting] = useState(false);
  const [isTelegramDisconnecting, setIsTelegramDisconnecting] = useState(false);

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
  });

  const { data: saxoStatus } = useQuery({
    queryKey: ['saxo-status'],
    queryFn: getSaxoStatus,
  });

  const { data: saxoConfigData } = useQuery({
    queryKey: ['saxo-config'],
    queryFn: getSaxoConfig,
  });

  const { data: ibkrStatus } = useQuery({
    queryKey: ['ibkr-status'],
    queryFn: getIBKRStatus,
  });

  const { data: ibkrConfigData } = useQuery({
    queryKey: ['ibkr-config'],
    queryFn: getIBKRConfig,
  });

  const { data: telegramConfigData } = useQuery({
    queryKey: ['telegram-config'],
    queryFn: getTelegramConfig,
  });

  const { data: brokerDetails } = useQuery({
    queryKey: ['brokers', 'details'],
    queryFn: getBrokerDetails,
  });

  const [cashEdits, setCashEdits] = useState<Record<string, { currency: string; balance: string }[]>>({});
  const [cashSaved, setCashSaved] = useState<Record<string, boolean>>({});
  const [accountTypeSaved, setAccountTypeSaved] = useState<Record<string, boolean>>({});

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

  useEffect(() => {
    if (settings) {
      setDateFormat(settings.date_format);
      setFinnhubApiKey(settings.finnhub_api_key || '');
      setOpenfigiApiKey(settings.openfigi_api_key || '');
    }
  }, [settings]);

  useEffect(() => {
    if (saxoConfigData) {
      setSaxoConfig(saxoConfigData);
    }
  }, [saxoConfigData]);

  useEffect(() => {
    if (ibkrConfigData) {
      setIbkrConfig(ibkrConfigData);
    }
  }, [ibkrConfigData]);

  useEffect(() => {
    if (telegramConfigData) {
      setTelegramConfig(telegramConfigData);
    }
  }, [telegramConfigData]);

  const mutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      saveDateFormat(data.date_format);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const brokerMutation = useMutation({
    mutationFn: createBroker,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['brokers'] });
      setNewBroker('');
    },
  });

  const resetMutation = useMutation({
    mutationFn: resetDatabase,
    onSuccess: () => {
      queryClient.invalidateQueries();
      setShowResetConfirm(false);
      setResetConfirmText('');
      setResetSuccess(true);
      setTimeout(() => setResetSuccess(false), 3000);
    },
  });

  const handleSave = () => {
    mutation.mutate({
      date_format: dateFormat,
      finnhub_api_key: finnhubApiKey || null,
      openfigi_api_key: openfigiApiKey || null,
    });
  };

  const handleAddBroker = (e: React.FormEvent) => {
    e.preventDefault();
    if (newBroker.trim()) {
      brokerMutation.mutate(newBroker.trim());
    }
  };

  const handleTestApi = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const result = await testFinnhubApi();
      setTestResult({ success: true, message: result.message });
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'API test mislukt';
      setTestResult({ success: false, message: errorMessage });
    } finally {
      setIsTesting(false);
    }
  };

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

  // IBKR handlers
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

  // Telegram handlers
  const handleSaveTelegramConfig = async () => {
    setIsSavingTelegramConfig(true);
    setTelegramMessage(null);
    try {
      await saveTelegramConfig(telegramConfig);
      queryClient.invalidateQueries({ queryKey: ['telegram-config'] });
      setTelegramConfigSaved(true);
      setTimeout(() => setTelegramConfigSaved(false), 2000);
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'Opslaan mislukt';
      setTelegramMessage({ success: false, message: errorMessage });
    } finally {
      setIsSavingTelegramConfig(false);
    }
  };

  const handleTelegramTest = async () => {
    setIsTelegramTesting(true);
    setTelegramMessage(null);
    try {
      const result = await testTelegram();
      setTelegramMessage({ success: true, message: result.message });
      setTimeout(() => setTelegramMessage(null), 5000);
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'Test mislukt';
      setTelegramMessage({ success: false, message: errorMessage });
    } finally {
      setIsTelegramTesting(false);
    }
  };

  const handleTelegramDisconnect = async () => {
    setIsTelegramDisconnecting(true);
    setTelegramMessage(null);
    try {
      await disconnectTelegram();
      setTelegramConfig({ bot_token: '', chat_id: '' });
      setTelegramMessage({ success: true, message: 'Telegram ontkoppeld' });
      queryClient.invalidateQueries({ queryKey: ['telegram-config'] });
      setTimeout(() => setTelegramMessage(null), 3000);
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || 'Ontkoppelen mislukt';
      setTelegramMessage({ success: false, message: errorMessage });
    } finally {
      setIsTelegramDisconnecting(false);
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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <SettingsIcon className="h-8 w-8 text-primary" />
        <h1 className="text-3xl font-bold">Instellingen</h1>
      </div>

      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">Weergave</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Datumnotatie
            </label>
            <div className="space-y-2">
              {dateFormats.map((format) => (
                <label
                  key={format.value}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    dateFormat === format.value
                      ? 'border-primary bg-primary/10'
                      : 'border-border hover:border-primary/50'
                  }`}
                >
                  <input
                    type="radio"
                    name="dateFormat"
                    value={format.value}
                    checked={dateFormat === format.value}
                    onChange={(e) => setDateFormat(e.target.value)}
                    className="sr-only"
                  />
                  <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                    dateFormat === format.value ? 'border-primary' : 'border-muted-foreground'
                  }`}>
                    {dateFormat === format.value && (
                      <div className="w-2 h-2 rounded-full bg-primary" />
                    )}
                  </div>
                  <div className="flex-1">
                    <div className="font-medium">{format.label}</div>
                    <div className="text-sm text-muted-foreground">
                      Voorbeeld: {format.example}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-6 flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={mutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {saved ? (
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
      </div>

      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">API Instellingen</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Finnhub API Key
            </label>
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <input
                  type={showApiKey ? "text" : "password"}
                  value={finnhubApiKey}
                  onChange={(e) => {
                    setFinnhubApiKey(e.target.value);
                    setTestResult(null);
                  }}
                  placeholder="Voer je Finnhub API key in..."
                  className="w-full px-3 py-2 pr-10 border rounded-md bg-background"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  title={showApiKey ? "Verberg API key" : "Toon API key"}
                >
                  {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <button
                type="button"
                onClick={handleTestApi}
                disabled={isTesting || !finnhubApiKey}
                className="flex items-center gap-2 px-4 py-2 border rounded-md hover:bg-accent transition-colors disabled:opacity-50"
                title="Test Finnhub API"
              >
                <TestTube2 className={`h-4 w-4 ${isTesting ? 'animate-pulse' : ''}`} />
                Test
              </button>
            </div>
            {testResult && (
              <div className={`mt-2 p-3 rounded-md text-sm ${
                testResult.success
                  ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-200'
                  : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-200'
              }`}>
                {testResult.message}
              </div>
            )}
            <p className="text-xs text-muted-foreground mt-2">
              Finnhub wordt gebruikt als fallback voor aandelen die niet gevonden worden via Yahoo Finance.
              Europese ISIN nummers worden bij voorkeur via Finnhub opgezocht.
              <br />
              <a
                href="https://finnhub.io/register"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                Registreer gratis bij Finnhub →
              </a>
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              OpenFIGI API Key (optioneel)
            </label>
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <input
                  type={showOpenfigiKey ? "text" : "password"}
                  value={openfigiApiKey}
                  onChange={(e) => setOpenfigiApiKey(e.target.value)}
                  placeholder="Voer je OpenFIGI API key in..."
                  className="w-full px-3 py-2 pr-10 border rounded-md bg-background"
                />
                <button
                  type="button"
                  onClick={() => setShowOpenfigiKey(!showOpenfigiKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  title={showOpenfigiKey ? "Verberg API key" : "Toon API key"}
                >
                  {showOpenfigiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Verhoogt rate limits. Werkt ook zonder key (25 req/min).
              OpenFIGI wordt gebruikt om ISIN/naam naar ticker te vertalen.
              <br />
              <a
                href="https://www.openfigi.com/user/signup"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                Registreer gratis bij OpenFIGI →
              </a>
            </p>
          </div>
        </div>

        <div className="mt-6 flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={mutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {saved ? (
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
      </div>

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
                          <li>{saxoSyncResult.dividends.imported} nieuwe dividenden geïmporteerd</li>
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
                  <p>{importResult.imported_stocks} effecten en {importResult.imported_transactions} transacties geïmporteerd</p>
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
                <li>{ibkrSyncResult.transactions_imported} transacties geïmporteerd</li>
                <li>{ibkrSyncResult.dividends_imported} dividenden geïmporteerd</li>
                <li>{ibkrSyncResult.cash_imported} kasbewegingen geïmporteerd</li>
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

      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Bell className="h-5 w-5 text-primary" />
            <h2 className="text-xl font-semibold">Telegram Alerts</h2>
          </div>
          {telegramConfig.bot_token && telegramConfig.chat_id && (
            <span className="text-xs px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded-full">
              Geconfigureerd
            </span>
          )}
        </div>

        <div className="space-y-4">
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Bot Token</label>
              <div className="relative">
                <input
                  type={showTelegramToken ? "text" : "password"}
                  value={telegramConfig.bot_token}
                  onChange={(e) => setTelegramConfig(prev => ({ ...prev, bot_token: e.target.value }))}
                  placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
                  className="w-full px-3 py-2 pr-10 border rounded-md bg-background text-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowTelegramToken(!showTelegramToken)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showTelegramToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Chat ID</label>
              <input
                type="text"
                value={telegramConfig.chat_id}
                onChange={(e) => setTelegramConfig(prev => ({ ...prev, chat_id: e.target.value }))}
                placeholder="-1001234567890 of je persoonlijke chat ID"
                className="w-full px-3 py-2 border rounded-md bg-background text-sm"
              />
            </div>
            <button
              onClick={handleSaveTelegramConfig}
              disabled={isSavingTelegramConfig || !telegramConfig.bot_token || !telegramConfig.chat_id}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50 text-sm"
            >
              {telegramConfigSaved ? (
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

          {telegramMessage && (
            <div className={`p-3 rounded-md text-sm ${
              telegramMessage.success
                ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-200'
                : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-200'
            }`}>
              {telegramMessage.message}
            </div>
          )}

          <div className="flex items-center gap-3 flex-wrap">
            <button
              type="button"
              onClick={handleTelegramTest}
              disabled={isTelegramTesting || !telegramConfig.bot_token || !telegramConfig.chat_id}
              className="flex items-center gap-2 px-4 py-2 border rounded-md hover:bg-accent transition-colors disabled:opacity-50 text-sm"
              title="Stuur testbericht"
            >
              <TestTube2 className={`h-4 w-4 ${isTelegramTesting ? 'animate-pulse' : ''}`} />
              Test versturen
            </button>
            {telegramConfig.bot_token && telegramConfig.chat_id && (
              <button
                type="button"
                onClick={handleTelegramDisconnect}
                disabled={isTelegramDisconnecting}
                className="flex items-center gap-2 px-4 py-2 border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50 text-sm"
                title="Telegram ontkoppelen"
              >
                <LogOut className={`h-4 w-4 ${isTelegramDisconnecting ? 'animate-pulse' : ''}`} />
                Ontkoppel
              </button>
            )}
          </div>

          <div className="p-3 bg-muted/30 rounded-md">
            <p className="text-xs text-muted-foreground">
              <strong>Telegram Bot instellen:</strong>
              <br />1. Open Telegram en zoek <strong>@BotFather</strong>
              <br />2. Stuur <code>/newbot</code> en volg de instructies
              <br />3. Kopieer de Bot Token hierboven
              <br />4. Stuur een bericht naar je bot zodat de chat actief is
              <br />5. Chat ID vinden: stuur een bericht naar je bot, ga naar
              {' '}<code>https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</code>
              {' '}en zoek <code>"chat":{"{"}"id":...</code>
              <br />6. Klik op "Test versturen" om de koppeling te verifiëren
            </p>
          </div>
        </div>
      </div>

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
                                value={broker.account_type || 'Privé'}
                                onChange={(e) => handleAccountTypeChange(broker.broker_name, e.target.value)}
                                className="px-2 py-1 border rounded-md bg-background text-sm"
                              >
                                <option value="Privé">Privé</option>
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

      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">Koers Lookup - Documentatie</h2>

        <div className="space-y-4 text-sm">
          <div>
            <h3 className="font-semibold mb-2 flex items-center gap-2">
              <Zap className="h-4 w-4 text-primary" />
              Automatische Koersen
            </h3>
            <p className="text-muted-foreground mb-2">
              De applicatie haalt automatisch koersen op via Yahoo Finance en Finnhub (indien API key is ingesteld).
            </p>
            <ul className="list-disc list-inside text-muted-foreground space-y-1 ml-4">
              <li><strong>Europese ISINs</strong> (IE, NL, DE, FR, BE, GB, etc.): Finnhub eerst, Yahoo Finance als fallback</li>
              <li><strong>Amerikaanse ISINs</strong>: Yahoo Finance eerst, Finnhub als fallback</li>
              <li><strong>Voorkeur voor EUR</strong>: Voor Europese ISINs wordt automatisch gezocht naar EUR-denominaties</li>
            </ul>
          </div>

          <div>
            <h3 className="font-semibold mb-2">Ondersteunde Beurzen (Yahoo Finance)</h3>
            <div className="grid grid-cols-2 gap-2 text-muted-foreground">
              <div>
                <span className="font-medium">Europa:</span>
                <ul className="list-disc list-inside ml-4">
                  <li>.DE - XETRA (Duitsland)</li>
                  <li>.AS - Euronext Amsterdam</li>
                  <li>.PA - Euronext Paris</li>
                  <li>.BR - Euronext Brussels</li>
                  <li>.MI - Borsa Italiana</li>
                </ul>
              </div>
              <div>
                <span className="font-medium">Overig:</span>
                <ul className="list-disc list-inside ml-4">
                  <li>.L - London Stock Exchange</li>
                  <li>.SW - SIX Swiss Exchange</li>
                  <li>US tickers zonder suffix</li>
                </ul>
              </div>
            </div>
          </div>

          <div>
            <h3 className="font-semibold mb-2 flex items-center gap-2">
              <Hand className="h-4 w-4 text-primary" />
              Handmatige Koersen
            </h3>
            <p className="text-muted-foreground mb-2">
              Als automatische lookup niet werkt of geen correcte data geeft:
            </p>
            <ol className="list-decimal list-inside text-muted-foreground space-y-1 ml-4">
              <li>Ga naar de detail pagina van het aandeel</li>
              <li>Klik op "Bewerken" of "Instellingen"</li>
              <li>Schakel "Handmatige Koers Tracking" in</li>
              <li>Voeg de huidige koers toe onder "Handmatige Koersen"</li>
              <li>Update de koers regelmatig (geel &gt; 1 dag, oranje &gt; 1 week, rood &gt; 2 weken)</li>
            </ol>
          </div>

          <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-md">
            <h3 className="font-semibold mb-1 text-amber-900 dark:text-amber-100">💡 Best Practice voor EU Aandelen</h3>
            <p className="text-xs text-amber-800 dark:text-amber-200">
              Voor Europese aandelen/ETFs: voeg de <strong>volledige ticker</strong> toe inclusief beurs-suffix
              (bijv. VVMX.DE in plaats van VVMX). Zo weet de applicatie exact welke beurs en valuta te gebruiken.
              <br /><br />
              <strong>Voorbeeld:</strong> VanEck Rare Earth ETF (ISIN: IE0002PG6CA6) → gebruik ticker <code className="px-1 py-0.5 bg-amber-100 dark:bg-amber-800 rounded">VVMX.DE</code> voor XETRA in EUR.
            </p>
          </div>
        </div>
      </div>

      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center gap-2 mb-4">
          <Trash2 className="h-5 w-5 text-red-500" />
          <h2 className="text-xl font-semibold">Gegevensbeheer</h2>
        </div>

        <p className="text-sm text-muted-foreground mb-4">
          Verwijder alle transacties, dividenden, effecten en koersdata. Instellingen en brokers blijven behouden.
        </p>

        {resetSuccess && (
          <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-md text-sm text-green-700 dark:text-green-300 flex items-center gap-2">
            <Check className="h-4 w-4" />
            Alle gegevens zijn gewist.
          </div>
        )}

        {resetMutation.error && (
          <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md text-sm text-red-700 dark:text-red-300">
            Fout: {(resetMutation.error as Error).message}
          </div>
        )}

        {!showResetConfirm ? (
          <button
            onClick={() => setShowResetConfirm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
          >
            <Trash2 className="h-4 w-4" />
            Database wissen
          </button>
        ) : (
          <div className="p-4 border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/20 rounded-lg space-y-3">
            <div className="flex items-start gap-2 text-red-700 dark:text-red-300">
              <AlertTriangle className="h-5 w-5 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Dit kan niet ongedaan worden gemaakt!</p>
                <p className="text-sm mt-1">
                  Alle transacties, dividenden, kasbewegingen, effecten en koersdata worden permanent verwijderd.
                </p>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-red-700 dark:text-red-300 mb-1">
                Typ <strong>WISSEN</strong> om te bevestigen:
              </label>
              <input
                type="text"
                value={resetConfirmText}
                onChange={(e) => setResetConfirmText(e.target.value)}
                placeholder="WISSEN"
                className="w-48 px-3 py-2 border border-red-300 dark:border-red-700 rounded-md bg-background text-sm"
                autoFocus
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => resetMutation.mutate()}
                disabled={resetConfirmText !== 'WISSEN' || resetMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {resetMutation.isPending ? 'Bezig met wissen...' : 'Definitief wissen'}
              </button>
              <button
                onClick={() => { setShowResetConfirm(false); setResetConfirmText(''); }}
                className="px-4 py-2 border border-border rounded-md hover:bg-accent transition-colors"
              >
                Annuleren
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">Over</h2>
        <p className="text-muted-foreground">
          Portfolio Tracker v2.0 - Een applicatie voor Belgische beleggers om aandelen,
          dividenden en transacties te beheren over meerdere brokers.
        </p>
      </div>
    </div>
  );
}
