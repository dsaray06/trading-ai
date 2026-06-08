// Colored pill for a recommendation action.

const COLORS: Record<string, string> = {
  Buy: "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
  "Buy Call": "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
  "Buy ETF": "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
  Add: "bg-green-100 text-green-800 ring-green-600/20",
  Hold: "bg-slate-100 text-slate-700 ring-slate-500/20",
  Watchlist: "bg-slate-100 text-slate-700 ring-slate-500/20",
  Trim: "bg-amber-100 text-amber-800 ring-amber-600/20",
  Hedge: "bg-amber-100 text-amber-800 ring-amber-600/20",
  Sell: "bg-rose-100 text-rose-800 ring-rose-600/20",
  "Buy Put": "bg-rose-100 text-rose-800 ring-rose-600/20",
};

export function ActionBadge({ action, large }: { action: string; large?: boolean }) {
  const color = COLORS[action] ?? "bg-slate-100 text-slate-700 ring-slate-500/20";
  const size = large ? "px-3 py-1 text-base" : "px-2 py-0.5 text-xs";
  return (
    <span
      className={`inline-flex items-center rounded-full font-semibold ring-1 ring-inset ${size} ${color}`}
    >
      {action}
    </span>
  );
}
