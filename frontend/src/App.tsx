import { Routes, Route, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import Dashboard from '@/pages/Dashboard';
import StockDetail from '@/pages/StockDetail';
import Dividends from '@/pages/Dividends';
import Analysis from '@/pages/Analysis';
import Settings from '@/pages/Settings';
import Watchlist from '@/pages/Watchlist';
import Import from '@/pages/Import';
import { saxoCallback } from '@/api/client';
import { Moon, Sun, TrendingUp, Settings as SettingsIcon, Upload } from 'lucide-react';

function App() {
  const navigate = useNavigate();
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('darkMode');
    return saved ? JSON.parse(saved) : true;
  });

  // Handle Saxo OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    if (code) {
      // Clean URL immediately
      window.history.replaceState({}, '', window.location.pathname);
      // Exchange code for tokens
      saxoCallback(code)
        .then(() => {
          localStorage.setItem('saxo_oauth_result', JSON.stringify({ success: true, message: 'Saxo verbinding succesvol!' }));
          navigate('/settings');
        })
        .catch((error) => {
          const message = error?.response?.data?.detail || 'OAuth koppeling mislukt';
          localStorage.setItem('saxo_oauth_result', JSON.stringify({ success: false, message }));
          navigate('/settings');
        });
    }
  }, [navigate]);

  useEffect(() => {
    localStorage.setItem('darkMode', JSON.stringify(darkMode));
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [darkMode]);

  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="border-b border-border">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-6 w-6 text-primary" />
              <span className="font-bold text-xl">Portfolio Tracker</span>
            </div>

            <div className="flex items-center gap-6">
              <a href="/" className="text-sm font-medium hover:text-primary transition-colors">
                Dashboard
              </a>
              <a href="/watchlist" className="text-sm font-medium hover:text-primary transition-colors">
                Watchlist
              </a>
              <a href="/dividends" className="text-sm font-medium hover:text-primary transition-colors">
                Dividenden
              </a>
              <a href="/analysis" className="text-sm font-medium hover:text-primary transition-colors">
                Analyse
              </a>
              <a href="/import" className="text-sm font-medium hover:text-primary transition-colors flex items-center gap-1">
                <Upload className="h-4 w-4" />
                Import
              </a>
              <a href="/settings" className="text-sm font-medium hover:text-primary transition-colors">
                <SettingsIcon className="h-5 w-5" />
              </a>

              <button
                onClick={() => setDarkMode(!darkMode)}
                className="p-2 rounded-md hover:bg-accent transition-colors"
              >
                {darkMode ? (
                  <Sun className="h-5 w-5" />
                ) : (
                  <Moon className="h-5 w-5" />
                )}
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/stock/:ticker" element={<StockDetail />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/dividends" element={<Dividends />} />
          <Route path="/analysis" element={<Analysis />} />
          <Route path="/import" element={<Import />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
