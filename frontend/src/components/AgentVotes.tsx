// Per-agent vote breakdown — the explainability surface (a product requirement).
import type { AgentVote } from "@/types/research";
import { ActionBadge } from "@/components/ActionBadge";

export function AgentVotes({ votes }: { votes: AgentVote[] }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Agent Vote Breakdown
      </h3>
      <div className="space-y-3">
        {votes.map((v) => (
          <div key={v.agent} className="rounded-md bg-slate-50 p-3">
            <div className="flex items-center justify-between">
              <span className="font-medium capitalize text-slate-800">{v.agent}</span>
              <div className="flex items-center gap-2">
                <ActionBadge action={v.action} />
                <span className="font-mono text-sm text-slate-600">
                  {v.score.toFixed(0)}/100
                </span>
                <span className="text-xs text-slate-400">
                  w {(v.weight * 100).toFixed(0)}%
                </span>
              </div>
            </div>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">{v.reasoning}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
