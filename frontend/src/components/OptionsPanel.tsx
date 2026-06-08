// Options Analysis panel: recommended contract, Greeks, and risk/reward.
import type { OptionsAnalysis } from "@/types/research";
import { ActionBadge } from "@/components/ActionBadge";

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="font-mono text-sm text-slate-800">{value}</div>
    </div>
  );
}

const money = (n: number | null | undefined) =>
  n == null ? "—" : `$${n.toFixed(2)}`;

export function OptionsPanel({ data }: { data: OptionsAnalysis }) {
  const g = data.greeks;
  const rr = data.risk_reward;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Options Analysis
        </h3>
        <ActionBadge action={data.action} />
      </div>

      <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
        <Cell label="Strike" value={`$${data.strike}`} />
        <Cell label="Expiration" value={data.expiration} />
        <Cell label="Premium" value={money(data.premium)} />
        <Cell
          label="Implied vol"
          value={data.implied_volatility != null ? `${(data.implied_volatility * 100).toFixed(0)}%` : "—"}
        />
      </div>

      <div className="mt-3 border-t border-slate-100 pt-3">
        <div className="text-xs uppercase tracking-wide text-slate-400">Greeks</div>
        <div className="mt-1 grid grid-cols-5 gap-2 text-center">
          {["delta", "gamma", "theta", "vega", "rho"].map((k) => (
            <div key={k}>
              <div className="text-xs capitalize text-slate-400">{k}</div>
              <div className="font-mono text-sm text-slate-800">
                {g[k] != null ? g[k].toFixed(3) : "—"}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 border-t border-slate-100 pt-3 sm:grid-cols-4">
        <Cell label="Max gain*" value={money(rr.max_gain)} />
        <Cell label="Max loss" value={money(rr.max_loss)} />
        <Cell label="Breakeven" value={money(rr.breakeven)} />
        <Cell label="Reward/Risk" value={rr.ratio != null ? `${rr.ratio.toFixed(1)}:1` : "—"} />
      </div>

      <p className="mt-3 text-xs text-slate-400">
        Contract {data.contract_symbol}. *Max gain estimated on a modeled favorable
        move; long options can lose the full premium. Paper / not financial advice.
      </p>
    </div>
  );
}
