// Compact panels for the Fundamental and Sentiment agents' analysis.
import type { FundamentalAnalysis, SentimentAnalysis } from "@/types/research";

function ScoreBar({ label, value }: { label: string; value: number }) {
  const color =
    value >= 66 ? "bg-emerald-500" : value >= 45 ? "bg-amber-400" : "bg-rose-500";
  return (
    <div className="mb-2 last:mb-0">
      <div className="flex justify-between text-sm">
        <span className="text-slate-500">{label}</span>
        <span className="font-mono text-slate-700">{value.toFixed(0)}</span>
      </div>
      <div className="mt-1 h-1.5 w-full rounded-full bg-slate-100">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

const PERCENT_KEYS = new Set([
  "profit_margin",
  "revenue_growth",
  "earnings_growth",
  "roe",
]);
const LABELS: Record<string, string> = {
  market_cap: "Market cap",
  pe: "P/E",
  forward_pe: "Forward P/E",
  pb: "P/B",
  profit_margin: "Profit margin",
  revenue_growth: "Revenue growth",
  earnings_growth: "Earnings growth",
  debt_to_equity: "Debt/equity",
  roe: "ROE",
  free_cash_flow: "Free cash flow",
};

function fmtMetric(key: string, v: number): string {
  if (PERCENT_KEYS.has(key)) return `${(v * 100).toFixed(1)}%`;
  if (key === "market_cap" || key === "free_cash_flow") {
    const abs = Math.abs(v);
    if (abs >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
    if (abs >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
    if (abs >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
    return `$${v.toFixed(0)}`;
  }
  return v.toFixed(2);
}

export function FundamentalPanel({ data }: { data: FundamentalAnalysis }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Fundamentals
      </h3>
      <ScoreBar label="Overall" value={data.fundamental_score} />
      <ScoreBar label="Valuation (higher = cheaper)" value={data.valuation_score} />
      <ScoreBar label="Quality" value={data.quality_score} />
      <ScoreBar label="Financial health" value={data.financial_health_score} />
      {Object.keys(data.metrics).length > 0 && (
        <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 border-t border-slate-100 pt-3">
          {Object.entries(data.metrics).map(([k, v]) => (
            <div key={k} className="flex justify-between text-sm">
              <span className="text-slate-500">{LABELS[k] ?? k}</span>
              <span className="font-mono text-slate-700">{fmtMetric(k, v)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function SentimentPanel({ data }: { data: SentimentAnalysis }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        News &amp; Sentiment
      </h3>
      <ScoreBar label="Sentiment" value={data.sentiment_score} />
      <ScoreBar label="Catalyst strength" value={data.catalyst_score} />
      <div className="mb-2">
        <div className="flex justify-between text-sm">
          <span className="text-slate-500">Risk (higher = riskier)</span>
          <span className="font-mono text-slate-700">{data.risk_score.toFixed(0)}</span>
        </div>
        <div className="mt-1 h-1.5 w-full rounded-full bg-slate-100">
          <div
            className="h-1.5 rounded-full bg-rose-400"
            style={{ width: `${data.risk_score}%` }}
          />
        </div>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">{data.news_summary}</p>
      {data.catalysts.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-600">
            Catalysts
          </p>
          <ul className="mt-1 list-disc pl-5 text-sm text-slate-600">
            {data.catalysts.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      )}
      {data.risks.length > 0 && (
        <div className="mt-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-rose-600">
            Risks
          </p>
          <ul className="mt-1 list-disc pl-5 text-sm text-slate-600">
            {data.risks.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
