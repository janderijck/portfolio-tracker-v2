import { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getTelegramConfig, saveTelegramConfig, testTelegram, disconnectTelegram } from '@/api/client';
import type { TelegramConfig } from '@/types';
import { Save, Check, Eye, EyeOff, TestTube2, Bell, LogOut } from 'lucide-react';

export default function TelegramSection() {
  const queryClient = useQueryClient();

  const [telegramConfig, setTelegramConfig] = useState<TelegramConfig>({ bot_token: '', chat_id: '' });
  const [showTelegramToken, setShowTelegramToken] = useState(false);
  const [telegramConfigSaved, setTelegramConfigSaved] = useState(false);
  const [isSavingTelegramConfig, setIsSavingTelegramConfig] = useState(false);
  const [telegramMessage, setTelegramMessage] = useState<{ success: boolean; message: string } | null>(null);
  const [isTelegramTesting, setIsTelegramTesting] = useState(false);
  const [isTelegramDisconnecting, setIsTelegramDisconnecting] = useState(false);

  const { data: telegramConfigData } = useQuery({
    queryKey: ['telegram-config'],
    queryFn: getTelegramConfig,
  });

  useEffect(() => {
    if (telegramConfigData) {
      setTelegramConfig(telegramConfigData);
    }
  }, [telegramConfigData]);

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

  return (
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
            <br />6. Klik op "Test versturen" om de koppeling te verifieren
          </p>
        </div>
      </div>
    </div>
  );
}
