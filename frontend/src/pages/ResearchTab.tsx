// Research tab: search a ticker, run the agent pipeline, render the explained
// recommendation + technical indicators + agent votes (docs/01-product-spec.md).
import { type FormEvent, useState } from "react";
import { AgentVotes } from "@/components/AgentVotes";
import { FundamentalPanel, SentimentPanel } from "@/components/AnalysisPanels";
import { IndicatorTable } from "@/components/IndicatorTable";
import { OptionsPanel } from "@/components/OptionsPanel";
import { RecommendationCard } from "@/components/RecommendationCard";
import { useResearch } from "@/hooks/useResearch";

export function ResearchTab() {
  const [ticker, setTicker] = useState("");
  const [includeOptions, setIncludeOptions] = useState(false);
  const { data, loading, error, run } = useResearch();

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void run(ticker, includeOptions);
  };

  return (
    <div className="mx-auto max-w-3xl">
      <form onSubmit={onSubmit} className="flex gap-2">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Search a ticker (e.g. AAPL)"
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 uppercase outline-none focus:border-slate-500 focus:ring-1 focus:ring-slate-500"
          aria-label="Ticker symbol"
        />
        <button
          type="submit"
          disabled={loading || !ticker.trim()}
          className="rounded-md bg-slate-900 px-5 py-2 font-medium text-white disabled:opacity-40"
        >
          {loading ? "Analyzing…" : "Research"}
        </button>
      </form>
      <label className="mt-2 flex items-center gap-2 text-sm text-slate-600">
        <input
          type="checkbox"
          checked={includeOptions}
          onChange={(e) => setIncludeOptions(e.target.checked)}
        />
        Include options analysis (Buy Call / Buy Put)
      </label>

      {error && (
        <div className="mt-4 rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      {loading && (
        <div className="mt-8 text-center text-slate-500">
          Running market analysis… this can take a few seconds.
        </div>
      )}

      {data && !loading && (
        <div className="mt-6 space-y-4">
          <RecommendationCard rec={data} />
          <AgentVotes votes={data.agent_votes} />
          {data.analysis.technical && <IndicatorTable ind={data.analysis.technical} />}
          {data.analysis.options && <OptionsPanel data={data.analysis.options} />}
          {data.analysis.fundamental && (
            <FundamentalPanel data={data.analysis.fundamental} />
          )}
          {data.analysis.sentiment && <SentimentPanel data={data.analysis.sentiment} />}
        </div>
      )}

      {!data && !loading && !error && (
        <p className="mt-12 text-center text-slate-400">
          Enter a ticker to generate an explainable technical recommendation.
        </p>
      )}
    </div>
  );
}
