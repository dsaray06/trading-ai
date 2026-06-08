// Headline recommendation: action, confidence, thesis, and reasoning report.
import type { Recommendation } from "@/types/research";
import { AcceptTradeButton } from "@/components/AcceptTradeButton";
import { ActionBadge } from "@/components/ActionBadge";

export function RecommendationCard({ rec }: { rec: Recommendation }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold text-slate-900">{rec.ticker}</h2>
            <ActionBadge action={rec.action} large />
            <span className="text-xs uppercase tracking-wide text-slate-400">
              {rec.asset_type}
            </span>
          </div>
          {rec.entry_target !== null && (
            <p className="mt-1 text-sm text-slate-500">
              Reference price ${rec.entry_target.toFixed(2)}
            </p>
          )}
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold text-slate-900">
            {rec.confidence.toFixed(0)}%
          </div>
          <div className="text-xs uppercase tracking-wide text-slate-400">confidence</div>
        </div>
      </div>

      <p className="mt-4 font-medium text-slate-800">{rec.thesis}</p>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">{rec.reasoning_report}</p>

      <AcceptTradeButton recommendationId={rec.id} action={rec.action} />

      <p className="mt-4 rounded bg-amber-50 px-3 py-2 text-xs text-amber-800">
        ⚠️ {rec.disclaimer}
      </p>
    </div>
  );
}
