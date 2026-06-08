// Three-tab shell (Research / Portfolio / Backtesting). Phase 1 fills in Research;
// the other tabs are placeholders for later phases (docs/07-roadmap.md).
import { useState } from "react";
import { BacktestingTab } from "@/pages/BacktestingTab";
import { PortfolioTab } from "@/pages/PortfolioTab";
import { ResearchTab } from "@/pages/ResearchTab";

const TABS = ["Research", "Portfolio", "Backtesting"] as const;
type Tab = (typeof TABS)[number];

export default function App() {
  const [tab, setTab] = useState<Tab>("Research");

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <h1 className="text-lg font-bold">
            Trading AI <span className="font-normal text-slate-400">· research</span>
          </h1>
          <nav className="flex gap-1">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                  tab === t
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {t}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="px-6 py-8">
        {tab === "Research" && <ResearchTab />}
        {tab === "Portfolio" && <PortfolioTab />}
        {tab === "Backtesting" && <BacktestingTab />}
      </main>
    </div>
  );
}
