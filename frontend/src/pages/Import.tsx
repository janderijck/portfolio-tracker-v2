/**
 * Import page - Upload and preview broker export files.
 *
 * Flow: Upload file -> Parse & preview (with duplicate detection) -> Review -> Confirm import
 */
import { useState, useCallback, useRef } from 'react';
import { Upload, FileSpreadsheet, AlertTriangle, CheckCircle, XCircle, ChevronDown, ChevronRight } from 'lucide-react';
import { useUploadImportFile, useConfirmImport } from '@/hooks/usePortfolio';
import { formatCurrency } from '@/utils/formatting';
import type {
  ImportPreviewResponse,
  ParsedTransaction,
  ParsedDividend,
  ParsedCashTransaction,
  ParsedStock,
} from '@/types';

type ImportStep = 'upload' | 'preview' | 'done';

export default function Import() {
  const [step, setStep] = useState<ImportStep>('upload');
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [selectedBroker, setSelectedBroker] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null!);

  // Selection state: which items to import (by index)
  const [selectedTx, setSelectedTx] = useState<Set<number>>(new Set());
  const [selectedDiv, setSelectedDiv] = useState<Set<number>>(new Set());
  const [selectedCash, setSelectedCash] = useState<Set<number>>(new Set());

  // Editable stocks state (for yahoo_ticker editing)
  const [editedStocks, setEditedStocks] = useState<ParsedStock[]>([]);

  // Collapsible sections
  const [showTransactions, setShowTransactions] = useState(true);
  const [showDividends, setShowDividends] = useState(true);
  const [showCash, setShowCash] = useState(true);
  const [showStocks, setShowStocks] = useState(false);
  const [showWarnings, setShowWarnings] = useState(true);

  const uploadMutation = useUploadImportFile();
  const confirmMutation = useConfirmImport();

  // ───────────────────────────────────────────────────────────────────────────
  // File handling
  // ───────────────────────────────────────────────────────────────────────────

  const handleFile = useCallback((file: File) => {
    uploadMutation.mutate(
      { file, broker: selectedBroker || undefined },
      {
        onSuccess: (data) => {
          setPreview(data);
          // Pre-select all non-duplicate items
          const txIndices = new Set<number>();
          data.transactions.forEach((t, i) => { if (!t.is_duplicate) txIndices.add(i); });
          setSelectedTx(txIndices);

          const divIndices = new Set<number>();
          data.dividends.forEach((d, i) => { if (!d.is_duplicate) divIndices.add(i); });
          setSelectedDiv(divIndices);

          const cashIndices = new Set<number>();
          data.cash_transactions.forEach((c, i) => { if (!c.is_duplicate) cashIndices.add(i); });
          setSelectedCash(cashIndices);

          setEditedStocks(data.stocks.map(s => ({ ...s })));
          // Auto-open stocks section if there are unresolved tickers
          if (data.stocks.some(s => !s.yahoo_ticker)) {
            setShowStocks(true);
          }
          setStep('preview');
        },
      }
    );
  }, [selectedBroker, uploadMutation]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const onFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }, [handleFile]);

  // ───────────────────────────────────────────────────────────────────────────
  // Selection helpers
  // ───────────────────────────────────────────────────────────────────────────

  const toggleItem = (set: Set<number>, setFn: React.Dispatch<React.SetStateAction<Set<number>>>, idx: number) => {
    const next = new Set(set);
    if (next.has(idx)) next.delete(idx);
    else next.add(idx);
    setFn(next);
  };

  const toggleAll = (
    items: { is_duplicate: boolean }[],
    set: Set<number>,
    setFn: React.Dispatch<React.SetStateAction<Set<number>>>,
  ) => {
    const nonDupIndices = items.map((_, i) => i).filter(i => !items[i].is_duplicate);
    const allSelected = nonDupIndices.every(i => set.has(i));
    if (allSelected) {
      setFn(new Set());
    } else {
      setFn(new Set(nonDupIndices));
    }
  };

  // ───────────────────────────────────────────────────────────────────────────
  // Confirm import
  // ───────────────────────────────────────────────────────────────────────────

  const handleConfirm = () => {
    if (!preview) return;

    const payload = {
      transactions: preview.transactions.filter((_, i) => selectedTx.has(i)),
      dividends: preview.dividends.filter((_, i) => selectedDiv.has(i)),
      cash_transactions: preview.cash_transactions.filter((_, i) => selectedCash.has(i)),
      stocks: editedStocks,
    };

    confirmMutation.mutate(payload, {
      onSuccess: () => {
        setStep('done');
      },
    });
  };

  const handleReset = () => {
    setStep('upload');
    setPreview(null);
    setSelectedTx(new Set());
    setSelectedDiv(new Set());
    setSelectedCash(new Set());
    setEditedStocks([]);
    uploadMutation.reset();
    confirmMutation.reset();
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ───────────────────────────────────────────────────────────────────────────
  // Render
  // ───────────────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Importeren</h1>

      {/* Step 1: Upload */}
      {step === 'upload' && (
        <UploadSection
          dragOver={dragOver}
          setDragOver={setDragOver}
          onDrop={onDrop}
          onFileSelect={onFileSelect}
          fileInputRef={fileInputRef}
          selectedBroker={selectedBroker}
          setSelectedBroker={setSelectedBroker}
          isLoading={uploadMutation.isPending}
          error={uploadMutation.error}
        />
      )}

      {/* Step 2: Preview */}
      {step === 'preview' && preview && (
        <div className="space-y-6">
          {/* Summary bar */}
          <PreviewSummary preview={preview} selectedTx={selectedTx} selectedDiv={selectedDiv} selectedCash={selectedCash} />

          {/* Warnings */}
          {preview.warnings.length > 0 && (
            <CollapsibleSection
              title={`Waarschuwingen (${preview.warnings.length})`}
              open={showWarnings}
              onToggle={() => setShowWarnings(!showWarnings)}
              variant="warning"
            >
              <ul className="space-y-1 text-sm text-yellow-700 dark:text-yellow-300">
                {preview.warnings.map((w, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                    {w}
                  </li>
                ))}
              </ul>
            </CollapsibleSection>
          )}

          {/* Transactions table */}
          {preview.transactions.length > 0 && (
            <CollapsibleSection
              title={`Transacties (${selectedTx.size}/${preview.transactions.length})`}
              open={showTransactions}
              onToggle={() => setShowTransactions(!showTransactions)}
            >
              <TransactionsTable
                items={preview.transactions}
                selected={selectedTx}
                onToggle={(i) => toggleItem(selectedTx, setSelectedTx, i)}
                onToggleAll={() => toggleAll(preview.transactions, selectedTx, setSelectedTx)}
              />
            </CollapsibleSection>
          )}

          {/* Dividends table */}
          {preview.dividends.length > 0 && (
            <CollapsibleSection
              title={`Dividenden (${selectedDiv.size}/${preview.dividends.length})`}
              open={showDividends}
              onToggle={() => setShowDividends(!showDividends)}
            >
              <DividendsTable
                items={preview.dividends}
                selected={selectedDiv}
                onToggle={(i) => toggleItem(selectedDiv, setSelectedDiv, i)}
                onToggleAll={() => toggleAll(preview.dividends, selectedDiv, setSelectedDiv)}
              />
            </CollapsibleSection>
          )}

          {/* Cash transactions table */}
          {preview.cash_transactions.length > 0 && (
            <CollapsibleSection
              title={`Kasbewegingen (${selectedCash.size}/${preview.cash_transactions.length})`}
              open={showCash}
              onToggle={() => setShowCash(!showCash)}
            >
              <CashTable
                items={preview.cash_transactions}
                selected={selectedCash}
                onToggle={(i) => toggleItem(selectedCash, setSelectedCash, i)}
                onToggleAll={() => toggleAll(preview.cash_transactions, selectedCash, setSelectedCash)}
              />
            </CollapsibleSection>
          )}

          {/* Stocks (info only) */}
          {preview.stocks.length > 0 && (
            <CollapsibleSection
              title={`Effecten (${preview.stocks.length})`}
              open={showStocks}
              onToggle={() => setShowStocks(!showStocks)}
            >
              <StocksTable
                items={editedStocks}
                onYahooTickerChange={(index, value) => {
                  setEditedStocks(prev => prev.map((s, i) =>
                    i === index ? { ...s, yahoo_ticker: value || null } : s
                  ));
                }}
                onTrackingChange={(index, manual) => {
                  setEditedStocks(prev => prev.map((s, i) =>
                    i === index ? { ...s, manual_price_tracking: manual } : s
                  ));
                }}
              />
            </CollapsibleSection>
          )}

          {/* Action buttons */}
          <div className="flex gap-4">
            <button
              onClick={handleConfirm}
              disabled={confirmMutation.isPending || (selectedTx.size === 0 && selectedDiv.size === 0 && selectedCash.size === 0)}
              className="px-6 py-2 bg-primary text-primary-foreground rounded-md font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {confirmMutation.isPending ? 'Importeren...' : `Importeer (${selectedTx.size + selectedDiv.size + selectedCash.size} items)`}
            </button>
            <button
              onClick={handleReset}
              className="px-6 py-2 border border-border rounded-md font-medium hover:bg-accent transition-colors"
            >
              Annuleren
            </button>
          </div>

          {confirmMutation.error && (
            <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300 text-sm">
              Fout bij importeren: {(confirmMutation.error as Error).message}
            </div>
          )}
        </div>
      )}

      {/* Step 3: Done */}
      {step === 'done' && confirmMutation.data && (
        <div className="p-6 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg space-y-4">
          <div className="flex items-center gap-2 text-green-700 dark:text-green-300">
            <CheckCircle className="h-6 w-6" />
            <span className="text-lg font-semibold">Import voltooid</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Transacties</span>
              <p className="font-semibold text-lg">{confirmMutation.data.imported.transactions}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Dividenden</span>
              <p className="font-semibold text-lg">{confirmMutation.data.imported.dividends}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Kasbewegingen</span>
              <p className="font-semibold text-lg">{confirmMutation.data.imported.cash_transactions}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Effecten</span>
              <p className="font-semibold text-lg">{confirmMutation.data.imported.stocks}</p>
            </div>
          </div>
          {confirmMutation.data.errors && confirmMutation.data.errors.length > 0 && (
            <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg space-y-2">
              <div className="flex items-center gap-2 text-yellow-700 dark:text-yellow-300 font-medium">
                <AlertTriangle className="h-4 w-4" />
                <span>{confirmMutation.data.errors.length} fout(en) bij importeren:</span>
              </div>
              <ul className="text-sm text-yellow-700 dark:text-yellow-300 space-y-1 ml-6 list-disc">
                {confirmMutation.data.errors.map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            </div>
          )}
          <button
            onClick={handleReset}
            className="px-6 py-2 bg-primary text-primary-foreground rounded-md font-medium hover:bg-primary/90 transition-colors"
          >
            Nieuw bestand importeren
          </button>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Upload Section
// =============================================================================

function UploadSection({
  dragOver, setDragOver, onDrop, onFileSelect, fileInputRef, selectedBroker, setSelectedBroker, isLoading, error,
}: {
  dragOver: boolean;
  setDragOver: (v: boolean) => void;
  onDrop: (e: React.DragEvent) => void;
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  fileInputRef: React.RefObject<HTMLInputElement>;
  selectedBroker: string;
  setSelectedBroker: (v: string) => void;
  isLoading: boolean;
  error: Error | null;
}) {
  return (
    <div className="space-y-4">
      {/* Broker selector */}
      <div className="flex items-center gap-4">
        <label className="text-sm font-medium">Broker:</label>
        <select
          value={selectedBroker}
          onChange={(e) => setSelectedBroker(e.target.value)}
          className="px-3 py-2 bg-background border border-border rounded-md text-sm"
        >
          <option value="">Automatisch detecteren</option>
          <option value="saxo">Saxo Bank</option>
          <option value="degiro">DEGIRO</option>
          <option value="ibkr">Interactive Brokers</option>
          <option value="traderepublic">Trade Republic</option>
          <option value="bolero">Bolero</option>
          <option value="kbc-prive">KBC Privé</option>
        </select>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`
          border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors
          ${dragOver
            ? 'border-primary bg-primary/5'
            : 'border-border hover:border-primary/50 hover:bg-accent/50'
          }
          ${isLoading ? 'opacity-50 pointer-events-none' : ''}
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.csv,.pdf"
          onChange={onFileSelect}
          className="hidden"
        />
        {isLoading ? (
          <div className="space-y-3">
            <div className="animate-spin h-10 w-10 border-4 border-primary border-t-transparent rounded-full mx-auto" />
            <p className="text-sm text-muted-foreground">Bestand verwerken...</p>
          </div>
        ) : (
          <div className="space-y-3">
            <Upload className="h-10 w-10 text-muted-foreground mx-auto" />
            <div>
              <p className="font-medium">Sleep een bestand hierheen</p>
              <p className="text-sm text-muted-foreground mt-1">of klik om te selecteren</p>
            </div>
            <p className="text-xs text-muted-foreground">
              Ondersteund: Saxo Bank (.xlsx), Trade Republic (.pdf), Bolero (.pdf)
            </p>
          </div>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-2 text-red-700 dark:text-red-300 text-sm">
          <XCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
          <span>{(error as any)?.response?.data?.detail || error.message}</span>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Preview Summary
// =============================================================================

function PreviewSummary({
  preview, selectedTx, selectedDiv, selectedCash,
}: {
  preview: ImportPreviewResponse;
  selectedTx: Set<number>;
  selectedDiv: Set<number>;
  selectedCash: Set<number>;
}) {
  return (
    <div className="p-4 bg-card border border-border rounded-lg">
      <div className="flex items-center gap-2 mb-3">
        <FileSpreadsheet className="h-5 w-5 text-primary" />
        <span className="font-semibold">Preview: {preview.broker}</span>
        {preview.skipped_rows > 0 && (
          <span className="text-xs text-muted-foreground">({preview.skipped_rows} rijen overgeslagen)</span>
        )}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
        <SummaryCard
          label="Transacties"
          total={preview.summary.total_transactions}
          selected={selectedTx.size}
          duplicates={preview.summary.duplicate_transactions}
        />
        <SummaryCard
          label="Dividenden"
          total={preview.summary.total_dividends}
          selected={selectedDiv.size}
          duplicates={preview.summary.duplicate_dividends}
        />
        <SummaryCard
          label="Kasbewegingen"
          total={preview.summary.total_cash}
          selected={selectedCash.size}
          duplicates={0}
        />
        <SummaryCard
          label="Effecten"
          total={preview.summary.total_stocks}
          selected={preview.summary.total_stocks}
          duplicates={0}
        />
      </div>
    </div>
  );
}

function SummaryCard({ label, total, selected, duplicates }: { label: string; total: number; selected: number; duplicates: number }) {
  return (
    <div>
      <span className="text-muted-foreground">{label}</span>
      <p className="font-semibold text-lg">{selected} / {total}</p>
      {duplicates > 0 && (
        <span className="text-xs text-yellow-600 dark:text-yellow-400">{duplicates} duplicaten</span>
      )}
    </div>
  );
}

// =============================================================================
// Collapsible Section
// =============================================================================

function CollapsibleSection({
  title, open, onToggle, variant, children,
}: {
  title: string;
  open: boolean;
  onToggle: () => void;
  variant?: 'warning';
  children: React.ReactNode;
}) {
  return (
    <div className={`border rounded-lg overflow-hidden ${
      variant === 'warning'
        ? 'border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-900/20'
        : 'border-border bg-card'
    }`}>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-4 py-3 text-left font-medium hover:bg-accent/50 transition-colors"
      >
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        {title}
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

// =============================================================================
// Transactions Table
// =============================================================================

function TransactionsTable({
  items, selected, onToggle, onToggleAll,
}: {
  items: ParsedTransaction[];
  selected: Set<number>;
  onToggle: (i: number) => void;
  onToggleAll: () => void;
}) {
  const nonDupCount = items.filter(t => !t.is_duplicate).length;
  const allSelected = nonDupCount > 0 && items.every((t, i) => t.is_duplicate || selected.has(i));

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th className="pb-2 pr-2">
              <input type="checkbox" checked={allSelected} onChange={onToggleAll} className="rounded" />
            </th>
            <th className="pb-2 pr-4">Datum</th>
            <th className="pb-2 pr-4">Type</th>
            <th className="pb-2 pr-4">Naam</th>
            <th className="pb-2 pr-4">Ticker</th>
            <th className="pb-2 pr-4 text-right">Aantal</th>
            <th className="pb-2 pr-4 text-right">Prijs</th>
            <th className="pb-2 pr-4">Valuta</th>
            <th className="pb-2 pr-4 text-right">Kosten</th>
            <th className="pb-2 pr-4 text-right">Belasting</th>
            <th className="pb-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((tx, i) => (
            <tr
              key={i}
              className={`border-b border-border/50 ${
                tx.is_duplicate
                  ? 'bg-yellow-50 dark:bg-yellow-900/10 text-muted-foreground'
                  : selected.has(i)
                  ? 'bg-green-50 dark:bg-green-900/10'
                  : ''
              }`}
            >
              <td className="py-2 pr-2">
                <input
                  type="checkbox"
                  checked={selected.has(i)}
                  onChange={() => onToggle(i)}
                  disabled={tx.is_duplicate}
                  className="rounded"
                />
              </td>
              <td className="py-2 pr-4 whitespace-nowrap">{tx.date}</td>
              <td className="py-2 pr-4">
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                  tx.transaction_type === 'BUY'
                    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                    : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                }`}>
                  {tx.transaction_type === 'BUY' ? 'Koop' : 'Verkoop'}
                </span>
              </td>
              <td className="py-2 pr-4 max-w-[200px] truncate" title={tx.name}>{tx.name}</td>
              <td className="py-2 pr-4 font-mono text-xs">{tx.ticker}</td>
              <td className="py-2 pr-4 text-right">{tx.quantity}</td>
              <td className="py-2 pr-4 text-right">{formatCurrency(tx.price_per_share, tx.currency)}</td>
              <td className="py-2 pr-4">{tx.currency}</td>
              <td className="py-2 pr-4 text-right">{tx.fees > 0 ? formatCurrency(tx.fees, tx.fees_currency) : '-'}</td>
              <td className="py-2 pr-4 text-right">{tx.taxes > 0 ? formatCurrency(tx.taxes, 'EUR') : '-'}</td>
              <td className="py-2">
                {tx.is_duplicate ? (
                  <span className="text-xs text-yellow-600 dark:text-yellow-400 font-medium">Duplicaat</span>
                ) : (
                  <span className="text-xs text-green-600 dark:text-green-400 font-medium">Nieuw</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// =============================================================================
// Dividends Table
// =============================================================================

function DividendsTable({
  items, selected, onToggle, onToggleAll,
}: {
  items: ParsedDividend[];
  selected: Set<number>;
  onToggle: (i: number) => void;
  onToggleAll: () => void;
}) {
  const nonDupCount = items.filter(d => !d.is_duplicate).length;
  const allSelected = nonDupCount > 0 && items.every((d, i) => d.is_duplicate || selected.has(i));

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th className="pb-2 pr-2">
              <input type="checkbox" checked={allSelected} onChange={onToggleAll} className="rounded" />
            </th>
            <th className="pb-2 pr-4">Datum</th>
            <th className="pb-2 pr-4">Ticker</th>
            <th className="pb-2 pr-4 text-right">Bruto</th>
            <th className="pb-2 pr-4 text-right">Bronbelasting</th>
            <th className="pb-2 pr-4 text-right">Netto</th>
            <th className="pb-2 pr-4">Valuta</th>
            <th className="pb-2 pr-4">Notities</th>
            <th className="pb-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((div, i) => (
            <tr
              key={i}
              className={`border-b border-border/50 ${
                div.is_duplicate
                  ? 'bg-yellow-50 dark:bg-yellow-900/10 text-muted-foreground'
                  : selected.has(i)
                  ? 'bg-green-50 dark:bg-green-900/10'
                  : ''
              }`}
            >
              <td className="py-2 pr-2">
                <input
                  type="checkbox"
                  checked={selected.has(i)}
                  onChange={() => onToggle(i)}
                  disabled={div.is_duplicate}
                  className="rounded"
                />
              </td>
              <td className="py-2 pr-4 whitespace-nowrap">{div.ex_date}</td>
              <td className="py-2 pr-4 font-mono text-xs">{div.ticker}</td>
              <td className="py-2 pr-4 text-right">{formatCurrency(div.bruto_amount, div.currency)}</td>
              <td className="py-2 pr-4 text-right">{div.withheld_tax > 0 ? formatCurrency(div.withheld_tax, div.currency) : '-'}</td>
              <td className="py-2 pr-4 text-right">{div.net_amount != null ? formatCurrency(div.net_amount, div.currency) : '-'}</td>
              <td className="py-2 pr-4">{div.currency}</td>
              <td className="py-2 pr-4 max-w-[200px] truncate text-xs text-muted-foreground" title={div.notes || ''}>{div.notes || '-'}</td>
              <td className="py-2">
                {div.is_duplicate ? (
                  <span className="text-xs text-yellow-600 dark:text-yellow-400 font-medium">Duplicaat</span>
                ) : (
                  <span className="text-xs text-green-600 dark:text-green-400 font-medium">Nieuw</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// =============================================================================
// Cash Transactions Table
// =============================================================================

function CashTable({
  items, selected, onToggle, onToggleAll,
}: {
  items: ParsedCashTransaction[];
  selected: Set<number>;
  onToggle: (i: number) => void;
  onToggleAll: () => void;
}) {
  const nonDupCount = items.filter(c => !c.is_duplicate).length;
  const allSelected = nonDupCount > 0 && items.every((c, i) => c.is_duplicate || selected.has(i));

  const typeLabel = (t: string) => {
    const map: Record<string, string> = {
      DEPOSIT: 'Storting',
      WITHDRAWAL: 'Opname',
      FX_CONVERSION: 'Wisselkoers',
      INTEREST: 'Rente',
      FEE: 'Kosten',
    };
    return map[t] || t;
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th className="pb-2 pr-2">
              <input type="checkbox" checked={allSelected} onChange={onToggleAll} className="rounded" />
            </th>
            <th className="pb-2 pr-4">Datum</th>
            <th className="pb-2 pr-4">Type</th>
            <th className="pb-2 pr-4 text-right">Bedrag</th>
            <th className="pb-2 pr-4">Valuta</th>
            <th className="pb-2 pr-4">Notities</th>
            <th className="pb-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((cash, i) => (
            <tr
              key={i}
              className={`border-b border-border/50 ${
                cash.is_duplicate
                  ? 'bg-yellow-50 dark:bg-yellow-900/10 text-muted-foreground'
                  : selected.has(i)
                  ? 'bg-green-50 dark:bg-green-900/10'
                  : ''
              }`}
            >
              <td className="py-2 pr-2">
                <input
                  type="checkbox"
                  checked={selected.has(i)}
                  onChange={() => onToggle(i)}
                  disabled={cash.is_duplicate}
                  className="rounded"
                />
              </td>
              <td className="py-2 pr-4 whitespace-nowrap">{cash.date}</td>
              <td className="py-2 pr-4">
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                  {typeLabel(cash.transaction_type)}
                </span>
              </td>
              <td className="py-2 pr-4 text-right">{formatCurrency(cash.amount, cash.currency)}</td>
              <td className="py-2 pr-4">{cash.currency}</td>
              <td className="py-2 pr-4 max-w-[300px] truncate text-xs text-muted-foreground" title={cash.notes || ''}>{cash.notes || '-'}</td>
              <td className="py-2">
                {cash.is_duplicate ? (
                  <span className="text-xs text-yellow-600 dark:text-yellow-400 font-medium">Duplicaat</span>
                ) : (
                  <span className="text-xs text-green-600 dark:text-green-400 font-medium">Nieuw</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// =============================================================================
// Stocks Table (info only, no selection)
// =============================================================================

function StocksTable({ items, onYahooTickerChange, onTrackingChange }: {
  items: ParsedStock[];
  onYahooTickerChange: (index: number, value: string) => void;
  onTrackingChange: (index: number, manual: boolean) => void;
}) {
  const hasUnresolved = items.some(s => !s.yahoo_ticker && !s.manual_price_tracking);

  return (
    <div className="space-y-2">
      {hasUnresolved && (
        <div className="flex items-center gap-2 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg text-yellow-700 dark:text-yellow-300 text-sm">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>Sommige effecten hebben geen Yahoo ticker. Vul een ticker in of kies 'Manueel' voor handmatige koersen.</span>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="pb-2 pr-4">Ticker</th>
              <th className="pb-2 pr-4">ISIN</th>
              <th className="pb-2 pr-4">Naam</th>
              <th className="pb-2 pr-4">Type</th>
              <th className="pb-2 pr-4">Valuta</th>
              <th className="pb-2 pr-4">Tracking</th>
              <th className="pb-2 pr-4">Yahoo Ticker</th>
              <th className="pb-2">Land</th>
            </tr>
          </thead>
          <tbody>
            {items.map((s, i) => (
              <tr key={i} className="border-b border-border/50">
                <td className="py-2 pr-4 font-mono text-xs">{s.ticker}</td>
                <td className="py-2 pr-4 font-mono text-xs">{s.isin}</td>
                <td className="py-2 pr-4">{s.name}</td>
                <td className="py-2 pr-4">{s.asset_type}</td>
                <td className="py-2 pr-4">{s.currency}</td>
                <td className="py-2 pr-4">
                  <select
                    value={s.manual_price_tracking ? 'manual' : 'auto'}
                    onChange={(e) => onTrackingChange(i, e.target.value === 'manual')}
                    className="px-2 py-1 text-xs border border-border rounded-md bg-background"
                  >
                    <option value="auto">Automatisch</option>
                    <option value="manual">Manueel</option>
                  </select>
                </td>
                <td className="py-2 pr-4">
                  <input
                    type="text"
                    value={s.yahoo_ticker || ''}
                    onChange={(e) => onYahooTickerChange(i, e.target.value)}
                    placeholder={s.manual_price_tracking ? '-' : 'bijv. AAPL'}
                    disabled={s.manual_price_tracking}
                    className={`w-28 px-2 py-1 font-mono text-xs border rounded-md bg-background ${
                      s.manual_price_tracking
                        ? 'border-border opacity-50 cursor-not-allowed'
                        : !s.yahoo_ticker
                        ? 'border-yellow-400 dark:border-yellow-600 bg-yellow-50 dark:bg-yellow-900/20'
                        : 'border-border'
                    }`}
                  />
                </td>
                <td className="py-2">{s.country}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
