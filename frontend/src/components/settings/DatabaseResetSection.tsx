import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { resetDatabase } from '@/api/client';
import { Check, Trash2, AlertTriangle } from 'lucide-react';

export default function DatabaseResetSection() {
  const queryClient = useQueryClient();

  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [resetConfirmText, setResetConfirmText] = useState('');
  const [resetSuccess, setResetSuccess] = useState(false);

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

  return (
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
  );
}
