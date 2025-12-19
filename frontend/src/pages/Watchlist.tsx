import { Link } from 'react-router-dom';
import { useWatchlist } from '@/hooks/usePortfolio';
import { Eye, Loader2, RefreshCw } from 'lucide-react';
import { getCurrencySymbol } from '@/utils/formatting';
import { useQueryClient } from '@tanstack/react-query';

export default function Watchlist() {
  const { data: watchlist, isLoading, isFetching } = useWatchlist();
  const queryClient = useQueryClient();

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['watchlist'] });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Eye className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold">Watchlist</h1>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isFetching}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          Koersen Verversen
        </button>
      </div>

      {!watchlist || watchlist.length === 0 ? (
        <div className="bg-card rounded-lg border p-8 text-center">
          <p className="text-muted-foreground">
            Geen aandelen in je watchlist. Voeg aandelen toe via het Dashboard zonder eerste aankoop.
          </p>
        </div>
      ) : (
        <div className="bg-card rounded-lg border">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-left p-4 font-medium">Aandeel</th>
                  <th className="text-left p-4 font-medium">ISIN</th>
                  <th className="text-right p-4 font-medium">Huidige Prijs</th>
                  <th className="text-left p-4 font-medium">Land</th>
                  <th className="text-center p-4 font-medium">Dividend</th>
                </tr>
              </thead>
              <tbody>
                {watchlist.map((stock: any) => (
                  <tr key={stock.ticker} className="border-b hover:bg-muted/50">
                    <td className="p-4">
                      <Link
                        to={`/stock/${stock.ticker}`}
                        className="text-primary hover:underline font-medium"
                      >
                        {stock.name}
                      </Link>
                      <div className="text-sm text-muted-foreground">{stock.ticker}</div>
                    </td>
                    <td className="p-4 text-sm text-muted-foreground">{stock.isin}</td>
                    <td className="p-4 text-right">
                      {stock.current_price
                        ? `${getCurrencySymbol(stock.currency)}${stock.current_price.toFixed(2)}`
                        : <span className="text-muted-foreground">N/A</span>
                      }
                    </td>
                    <td className="p-4">{stock.country}</td>
                    <td className="p-4 text-center">
                      {stock.pays_dividend && (
                        <span className="text-xs bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 px-2 py-0.5 rounded">
                          Dividend
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
