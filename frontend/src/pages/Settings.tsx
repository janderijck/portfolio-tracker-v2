import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSettings, updateSettings, getBrokers, createBroker, testFinnhubApi } from '@/api/client';
import { saveDateFormat } from '@/utils/formatting';
import { Settings as SettingsIcon, Save, Check, Plus, Building2, Zap, Hand, Eye, EyeOff, TestTube2 } from 'lucide-react';

const dateFormats = [
  { value: 'DD/MM/YYYY', label: 'DD/MM/YYYY (Europees)', example: '23/11/2025' },
  { value: 'MM/DD/YYYY', label: 'MM/DD/YYYY (Amerikaans)', example: '11/23/2025' },
  { value: 'YYYY-MM-DD', label: 'YYYY-MM-DD (ISO)', example: '2025-11-23' },
];

export default function Settings() {
  const queryClient = useQueryClient();
  const [dateFormat, setDateFormat] = useState('DD/MM/YYYY');
  const [finnhubApiKey, setFinnhubApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [saved, setSaved] = useState(false);
  const [newBroker, setNewBroker] = useState('');
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
  });

  const { data: brokers } = useQuery({
    queryKey: ['brokers'],
    queryFn: getBrokers,
  });

  useEffect(() => {
    if (settings) {
      setDateFormat(settings.date_format);
      setFinnhubApiKey(settings.finnhub_api_key || '');
    }
  }, [settings]);

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

  const handleSave = () => {
    mutation.mutate({
      date_format: dateFormat,
      finnhub_api_key: finnhubApiKey || null
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
        <div className="flex items-center gap-2 mb-4">
          <Building2 className="h-5 w-5 text-primary" />
          <h2 className="text-xl font-semibold">Brokers</h2>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Beschikbare brokers</label>
            <div className="flex flex-wrap gap-2 mb-4">
              {brokers?.map((broker) => (
                <span
                  key={broker}
                  className="px-3 py-1 bg-muted rounded-md text-sm"
                >
                  {broker}
                </span>
              ))}
              {(!brokers || brokers.length === 0) && (
                <span className="text-muted-foreground text-sm">Geen brokers</span>
              )}
            </div>
          </div>

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
        <h2 className="text-xl font-semibold mb-4">Over</h2>
        <p className="text-muted-foreground">
          Portfolio Tracker v2.0 - Een applicatie voor Belgische beleggers om aandelen,
          dividenden en transacties te beheren over meerdere brokers.
        </p>
      </div>
    </div>
  );
}
