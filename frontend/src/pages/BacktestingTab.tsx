// Backtesting tab: run a strategy vs a benchmark, chart the equity curve, and
// compare past runs. Strategies are deterministic technical rules (no look-ahead).
import { type FormEvent, type ReactNode, useCallback, useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiErrorMessage } from "@/api/client";
import { createBacktest, getBacktest, listBacktests } from "@/api/backtest";
import { useAuth } from "@/auth/AuthContext";
import { AuthPanel } from "@/components/AuthPanel";
import {
  type BacktestOut,
  type BacktestSummary,
  type Benchmark,
  type Horizon,
  STRATEGIES,
} from "@/types/backtest";

const pct = (n: number) => `${(n * 100).toFixed(1)}%`;
const num = (n: number) => n.toFixed(2);
const money = (n: number) =>
  n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const signClass = (n: number) => (n >= 0 ? "text-emerald-600" : "text-rose-600");

export function BacktestingTab() {
  const { user } = useAuth();
  if (!user) return <AuthPanel />;
  return <BacktestWorkspace />;
}

function BacktestWorkspace() {
  const [strategy, setStrategy] = useState("sma_crossover");
  const [symbol, setSymbol] = useState("AAPL");
  const [benchmark, setBenchmark] = useState<Benchmark>("SPY");
  const [horizon, setHorizon] = useState<Horizon>("3Y");
  const [result, setResult] = useState<BacktestOut | null>(null);
  const [runs, setRuns] = useState<BacktestSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshRuns = useCallback(async () => {
    try {
      setRuns(await listBacktests());
    } catch {
      /* non-fatal */
    }
  }, []);

  useEffect(() => {
    void refreshRuns();
  }, [refreshRuns]);

  const run = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const bt = await createBacktest({
        strategy,
        symbol: symbol.trim().toUpperCase(),
        benchmark,
        horizon,
      });
      setResult(bt);
      await refreshRuns();
    } catch (err) {
      setError(apiErrorMessage(err, "Backtest failed."));
    } finally {
      setLoading(false);
    }
  };

  const loadRun = async (id: string) => {
    try {
      setResult(await getBacktest(id));
    } catch (err) {
      setError(apiErrorMessage(err, "Could not load run."));
    }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <form
        onSubmit={run}
        className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4"
      >
        <Field label="Strategy">
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          >
            {STRATEGIES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Symbol">
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="w-24 rounded-md border border-slate-300 px-2 py-1.5 text-sm uppercase"
          />
        </Field>
        <Field label="Benchmark">
          <select
            value={benchmark}
            onChange={(e) => setBenchmark(e.target.value as Benchmark)}
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          >
            {(["SPY", "QQQ", "VTI"] as const).map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Horizon">
          <select
            value={horizon}
            onChange={(e) => setHorizon(e.target.value as Horizon)}
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          >
            {(["1Y", "3Y", "5Y", "10Y"] as const).map((h) => (
              <option key={h} value={h}>
                {h}
              </option>
            ))}
          </select>
        </Field>
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-slate-900 px-5 py-1.5 text-sm font-medium text-white disabled:opacity-40"
        >
          {loading ? "Running…" : "Run backtest"}
        </button>
      </form>

      {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}

      {result && <ResultView result={result} />}

      {runs.length > 0 && <RunsTable runs={runs} onSelect={loadRun} />}
    </div>
  );
}

function ResultView({ result }: { result: BacktestOut }) {
  const m = result.metrics;
  return (
    <div className="mt-4 space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="mb-1 text-sm font-semibold text-slate-700">
          {result.strategy_label} on {result.symbol} vs {result.benchmark} ·{" "}
          {result.horizon}
        </h3>
        <p className="mb-3 text-xs text-slate-400">
          {result.start_date} → {result.end_date}
        </p>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={result.equity_curve} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "#94a3b8" }}
              minTickGap={48}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "#94a3b8" }}
              tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
              width={48}
            />
            <Tooltip formatter={(v: number) => money(v)} />
            <Legend />
            <Line
              type="monotone"
              dataKey="strategy"
              name={result.strategy_label}
              stroke="#0f172a"
              dot={false}
              strokeWidth={2}
            />
            <Line
              type="monotone"
              dataKey="benchmark"
              name={result.benchmark}
              stroke="#94a3b8"
              dot={false}
              strokeWidth={1.5}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <Stat label="Total return" value={pct(m.total_return)} cls={signClass(m.total_return)} />
        <Stat label="Annualized" value={pct(m.annualized_return)} />
        <Stat
          label="vs Benchmark"
          value={pct(m.benchmark_adjusted_return)}
          cls={signClass(m.benchmark_adjusted_return)}
        />
        <Stat label="Sharpe" value={num(m.sharpe)} />
        <Stat label="Sortino" value={num(m.sortino)} />
        <Stat label="Max drawdown" value={pct(m.max_drawdown)} cls="text-rose-600" />
        <Stat label="Win rate" value={pct(m.win_rate)} />
        <Stat label="Profit factor" value={num(m.profit_factor)} />
        <Stat label="Trades" value={String(m.num_trades)} />
        <Stat label="Final value" value={money(m.final_value)} />
        <Stat label="Benchmark final" value={money(m.benchmark_final_value)} />
      </div>
    </div>
  );
}

function RunsTable({
  runs,
  onSelect,
}: {
  runs: BacktestSummary[];
  onSelect: (id: string) => void;
}) {
  return (
    <div className="mt-6 rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Past runs (click to view)
      </h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase text-slate-400">
            <th className="py-1">Strategy</th>
            <th>Symbol</th>
            <th>Bench</th>
            <th>Horizon</th>
            <th>Total</th>
            <th>vs Bench</th>
            <th>Sharpe</th>
            <th>Max DD</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr
              key={r.id}
              onClick={() => onSelect(r.id)}
              className="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
            >
              <td className="py-2">{r.strategy_label}</td>
              <td className="font-medium">{r.symbol}</td>
              <td>{r.benchmark}</td>
              <td>{r.horizon}</td>
              <td className={signClass(r.metrics.total_return ?? 0)}>
                {pct(r.metrics.total_return ?? 0)}
              </td>
              <td className={signClass(r.metrics.benchmark_adjusted_return ?? 0)}>
                {pct(r.metrics.benchmark_adjusted_return ?? 0)}
              </td>
              <td>{num(r.metrics.sharpe ?? 0)}</td>
              <td className="text-rose-600">{pct(r.metrics.max_drawdown ?? 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs uppercase tracking-wide text-slate-400">{label}</span>
      {children}
    </label>
  );
}

function Stat({ label, value, cls }: { label: string; value: string; cls?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`mt-1 text-lg font-semibold ${cls ?? "text-slate-900"}`}>{value}</div>
    </div>
  );
}
