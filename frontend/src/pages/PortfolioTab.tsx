// Portfolio tab: portfolios, holdings, allocation, trade history, holdings review.
import { type FormEvent, useCallback, useEffect, useState } from "react";
import { type AlpacaStatus, getAlpacaStatus } from "@/api/alpaca";
import { apiErrorMessage } from "@/api/client";
import { getPositions, getSummary, getTrades, reviewPortfolio } from "@/api/portfolio";
import { useAuth } from "@/auth/AuthContext";
import { ActionBadge } from "@/components/ActionBadge";
import { AuthPanel } from "@/components/AuthPanel";
import { ConnectAlpacaPanel } from "@/components/ConnectAlpacaPanel";
import { usePortfolios } from "@/hooks/usePortfolios";
import type {
  HoldingReviewItem,
  Portfolio,
  PortfolioSummary,
  Position,
  Trade,
} from "@/types/portfolio";

type CreateFn = (
  name: string,
  cash: number,
  broker: "simulated" | "alpaca",
) => Promise<Portfolio>;

const money = (n: number) =>
  n.toLocaleString(undefined, { style: "currency", currency: "USD" });
const pctClass = (n: number) => (n >= 0 ? "text-emerald-600" : "text-rose-600");

function num(risk: Record<string, unknown>, key: string): number {
  const v = risk[key];
  return typeof v === "number" ? v : 0;
}

export function PortfolioTab() {
  const { user, logout } = useAuth();
  if (!user) return <AuthPanel />;
  return <PortfolioWorkspace email={user.email} onLogout={logout} />;
}

function PortfolioWorkspace({
  email,
  onLogout,
}: {
  email: string;
  onLogout: () => void;
}) {
  const { portfolios, loading, create } = usePortfolios();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [alpaca, setAlpaca] = useState<AlpacaStatus | null>(null);
  const [showAlpaca, setShowAlpaca] = useState(false);

  useEffect(() => {
    if (!selectedId && portfolios.length > 0) setSelectedId(portfolios[0].id);
  }, [portfolios, selectedId]);

  useEffect(() => {
    getAlpacaStatus().then(setAlpaca).catch(() => {});
  }, []);

  const onCreated = (pf: Portfolio) => {
    setShowCreate(false);
    setSelectedId(pf.id);
  };

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {portfolios.length > 0 && (
            <select
              value={selectedId ?? ""}
              onChange={(e) => setSelectedId(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            >
              {portfolios.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                  {p.broker === "alpaca" ? " · Alpaca" : ""}
                </option>
              ))}
            </select>
          )}
          <button
            onClick={() => setShowCreate((v) => !v)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
          >
            + New
          </button>
        </div>
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <button onClick={() => setShowAlpaca((v) => !v)} className="hover:text-slate-800">
            {alpaca?.connected ? "🟢 Alpaca" : "Connect Alpaca"}
          </button>
          <span>{email}</span>
          <button onClick={onLogout} className="underline">
            Log out
          </button>
        </div>
      </div>

      {showAlpaca && alpaca && (
        <ConnectAlpacaPanel
          status={alpaca}
          onChange={setAlpaca}
          onClose={() => setShowAlpaca(false)}
        />
      )}

      {loading && <p className="text-slate-400">Loading…</p>}
      {(showCreate || (!loading && portfolios.length === 0)) && (
        <CreatePortfolioForm
          onCreate={create}
          onCreated={onCreated}
          alpacaConnected={alpaca?.connected ?? false}
        />
      )}
      {selectedId && <PortfolioDetail portfolioId={selectedId} />}
    </div>
  );
}

function CreatePortfolioForm({
  onCreate,
  onCreated,
  alpacaConnected,
}: {
  onCreate: CreateFn;
  onCreated: (pf: Portfolio) => void;
  alpacaConnected: boolean;
}) {
  const [name, setName] = useState("My Paper Portfolio");
  const [cash, setCash] = useState(100000);
  const [broker, setBroker] = useState<"simulated" | "alpaca">(
    alpacaConnected ? "alpaca" : "simulated",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const alpacaEnabled = alpacaConnected;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const pf = await onCreate(name, cash, broker);
      onCreated(pf);
    } catch (err) {
      setError(apiErrorMessage(err, "Could not create portfolio."));
    } finally {
      setBusy(false);
    }
  };

  const isAlpaca = broker === "alpaca";

  return (
    <form onSubmit={submit} className="mt-6 rounded-lg border border-slate-200 bg-white p-5">
      <h3 className="font-semibold text-slate-800">Create a portfolio</h3>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="flex-1 rounded-md border border-slate-300 px-3 py-2"
          placeholder="Portfolio name"
        />
        {alpacaEnabled && (
          <select
            value={broker}
            onChange={(e) => setBroker(e.target.value as "simulated" | "alpaca")}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="alpaca">Alpaca Paper</option>
            <option value="simulated">Simulated</option>
          </select>
        )}
        {!isAlpaca && (
          <input
            type="number"
            value={cash}
            min={1}
            onChange={(e) => setCash(Number(e.target.value))}
            className="w-36 rounded-md border border-slate-300 px-3 py-2"
          />
        )}
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-slate-900 px-4 py-2 font-medium text-white disabled:opacity-40"
        >
          {busy ? "…" : "Create"}
        </button>
      </div>
      {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
      <p className="mt-2 text-xs text-slate-400">
        {isAlpaca
          ? "Mirrors your Alpaca paper account — cash and positions come from Alpaca. Paper only."
          : "Starts with simulated cash. Trades are paper only — never real money."}
      </p>
    </form>
  );
}

function PortfolioDetail({ portfolioId }: { portfolioId: string }) {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [reviews, setReviews] = useState<Record<string, HoldingReviewItem>>({});
  const [error, setError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, p, t] = await Promise.all([
        getSummary(portfolioId),
        getPositions(portfolioId),
        getTrades(portfolioId),
      ]);
      setSummary(s);
      setPositions(p);
      setTrades(t);
    } catch (err) {
      setError(apiErrorMessage(err, "Could not load portfolio."));
    }
  }, [portfolioId]);

  useEffect(() => {
    setReviews({});
    void load();
  }, [load]);

  const runReview = async () => {
    setReviewing(true);
    try {
      const res = await reviewPortfolio(portfolioId);
      const map: Record<string, HoldingReviewItem> = {};
      for (const r of res.reviews) map[r.symbol] = r;
      setReviews(map);
    } catch (err) {
      setError(apiErrorMessage(err, "Review failed."));
    } finally {
      setReviewing(false);
    }
  };

  if (error) return <p className="mt-4 text-rose-600">{error}</p>;
  if (!summary) return <p className="mt-4 text-slate-400">Loading…</p>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Total value" value={money(summary.total_value)} />
        <Stat label="Cash" value={money(summary.cash_balance)} />
        <Stat
          label="Total P/L"
          value={money(summary.total_pl)}
          className={pctClass(summary.total_pl)}
        />
        <Stat label="Risk score" value={num(summary.risk, "risk_score").toFixed(0)} />
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Positions ({positions.length})
          </h3>
          {positions.length > 0 && (
            <button
              onClick={runReview}
              disabled={reviewing}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
            >
              {reviewing ? "Reviewing…" : "Run holdings review"}
            </button>
          )}
        </div>
        {positions.length === 0 ? (
          <p className="text-sm text-slate-400">
            No positions yet. Accept a recommendation from the Research tab to paper-trade.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-slate-400">
                <th className="py-1">Symbol</th>
                <th>Qty</th>
                <th>Avg</th>
                <th>Price</th>
                <th>Value</th>
                <th>Unreal. P/L</th>
                <th>AI review</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => {
                const review = reviews[p.symbol];
                return (
                  <tr key={p.id} className="border-t border-slate-100">
                    <td className="py-2 font-medium">{p.symbol}</td>
                    <td>{p.quantity}</td>
                    <td>{money(p.avg_cost)}</td>
                    <td>{money(p.current_price)}</td>
                    <td>{money(p.market_value)}</td>
                    <td className={pctClass(p.unrealized_pct)}>
                      {money(p.unrealized_pl)} ({p.unrealized_pct.toFixed(1)}%)
                    </td>
                    <td>{review ? <ActionBadge action={review.action} /> : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        {Object.values(reviews).map((r) => (
          <p key={r.symbol} className="mt-2 text-sm text-slate-600">
            <span className="font-medium">{r.symbol}:</span> {r.reasoning}
          </p>
        ))}
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Trade history ({trades.length})
        </h3>
        {trades.length === 0 ? (
          <p className="text-sm text-slate-400">No trades yet.</p>
        ) : (
          <table className="w-full text-sm">
            <tbody>
              {trades.map((t) => (
                <tr key={t.id} className="border-t border-slate-100">
                  <td className="py-2 capitalize">{t.side}</td>
                  <td className="font-medium">{t.symbol}</td>
                  <td>{t.quantity}</td>
                  <td>@ {money(t.price)}</td>
                  <td className="text-slate-400">
                    {new Date(t.executed_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`mt-1 text-lg font-semibold ${className ?? "text-slate-900"}`}>
        {value}
      </div>
    </div>
  );
}
