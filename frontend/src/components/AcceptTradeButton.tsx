// "Paper trade" control on the Research recommendation card.
// Closes the loop: accept a recommendation into one of the user's portfolios.
import { useEffect, useState } from "react";
import { apiErrorMessage } from "@/api/client";
import { acceptTrade, previewTrade } from "@/api/portfolio";
import { useAuth } from "@/auth/AuthContext";
import { usePortfolios } from "@/hooks/usePortfolios";
import type { TradePreview } from "@/types/portfolio";

const EXECUTABLE = new Set([
  "Buy", "Add", "Buy ETF", "Sell", "Trim", "Buy Call", "Buy Put",
]);

export function AcceptTradeButton({
  recommendationId,
  action,
}: {
  recommendationId: string;
  action: string;
}) {
  const { user } = useAuth();
  const { portfolios } = usePortfolios();
  const [portfolioId, setPortfolioId] = useState("");
  const [qty, setQty] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<TradePreview | null>(null);

  const selectedId = portfolioId || portfolios[0]?.id;

  // Fetch the auto-sized suggestion whenever the target portfolio changes, so the
  // user sees how much would be bought (and why) before committing.
  useEffect(() => {
    if (!user || !selectedId || !EXECUTABLE.has(action) || result) {
      setPreview(null);
      return;
    }
    let cancelled = false;
    previewTrade(selectedId, recommendationId)
      .then((p) => !cancelled && setPreview(p))
      .catch(() => !cancelled && setPreview(null));
    return () => {
      cancelled = true;
    };
  }, [user, selectedId, recommendationId, action, result]);

  if (!EXECUTABLE.has(action)) {
    return (
      <p className="mt-4 text-xs text-slate-400">
        “{action}” is not an executable equity trade (paper trading supports
        Buy/Add/Sell/Trim).
      </p>
    );
  }
  if (!user) {
    return (
      <p className="mt-4 text-xs text-slate-400">
        Log in on the Portfolio tab to paper-trade this recommendation.
      </p>
    );
  }
  if (portfolios.length === 0) {
    return (
      <p className="mt-4 text-xs text-slate-400">
        Create a portfolio on the Portfolio tab first, then come back to paper-trade.
      </p>
    );
  }

  const selected = selectedId;
  const unit = preview?.asset_type === "option" ? "contract" : "share";
  const autoQty = preview?.suggested_quantity ?? 0;

  const submit = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const t = await acceptTrade(
        selected,
        recommendationId,
        qty ? Number(qty) : undefined,
      );
      setResult(`Paper ${t.side} ${t.quantity} ${t.symbol} @ $${t.price.toFixed(2)}.`);
    } catch (err) {
      setError(apiErrorMessage(err, "Trade failed."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-slate-700">Paper trade:</span>
        <select
          value={selected}
          onChange={(e) => setPortfolioId(e.target.value)}
          className="rounded-md border border-slate-300 px-2 py-1 text-sm"
        >
          {portfolios.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <input
          type="number"
          min={1}
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          placeholder={autoQty > 0 ? `${autoQty} (auto)` : "qty (auto)"}
          className="w-28 rounded-md border border-slate-300 px-2 py-1 text-sm"
        />
        <button
          onClick={submit}
          disabled={busy}
          className="rounded-md bg-slate-900 px-3 py-1 text-sm font-medium text-white disabled:opacity-40"
        >
          {busy ? "…" : `Submit ${action}`}
        </button>
      </div>
      {preview && !result && (
        <p className="mt-2 text-xs text-slate-500">
          {preview.side === "buy" && autoQty > 0 ? (
            <>
              Suggested: <span className="font-medium text-slate-700">{autoQty} {unit}
              {autoQty === 1 ? "" : "s"}</span> ≈ ${preview.estimated_cost.toLocaleString()}{" "}
              ({preview.pct_of_portfolio}% of portfolio). Leave the box blank to use this,
              or enter your own.
            </>
          ) : (
            preview.note
          )}
        </p>
      )}
      {result && <p className="mt-2 text-sm text-emerald-700">{result}</p>}
      {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
    </div>
  );
}
