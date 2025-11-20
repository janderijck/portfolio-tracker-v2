import { Routes, Route } from 'react-router-dom';
import { useState, useEffect } from 'react';
import Dashboard from '@/pages/Dashboard';
import StockDetail from '@/pages/StockDetail';
import Dividends from '@/pages/Dividends';
import Analysis from '@/pages/Analysis';
import { Moon, Sun, TrendingUp } from 'lucide-react';

function App() {
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('darkMode');
    return saved ? JSON.parse(saved) : true;
  });

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
              <a href="/dividends" className="text-sm font-medium hover:text-primary transition-colors">
                Dividenden
              </a>
              <a href="/analysis" className="text-sm font-medium hover:text-primary transition-colors">
                Analyse
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
          <Route path="/dividends" element={<Dividends />} />
          <Route path="/analysis" element={<Analysis />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
