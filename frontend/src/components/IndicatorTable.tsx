// Technical indicator readout for the Research tab.
import type { TechnicalIndicators } from "@/types/research";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-1.5 last:border-0">
      <span className="text-sm text-slate-500">{label}</span>
      <span className="font-mono text-sm text-slate-800">{value}</span>
    </div>
  );
}

export function IndicatorTable({ ind }: { ind: TechnicalIndicators }) {
  const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Technical Indicators
      </h3>
      <Row label="Last price" value={`$${ind.last_price.toFixed(2)}`} />
      <Row label="SMA 20" value={`$${ind.sma_20.toFixed(2)}`} />
      <Row
        label="SMA 50"
        value={ind.sma_50 === null ? "—" : `$${ind.sma_50.toFixed(2)}`}
      />
      <Row label="EMA 12 / 26" value={`${ind.ema_12.toFixed(2)} / ${ind.ema_26.toFixed(2)}`} />
      <Row label="RSI (14)" value={ind.rsi_14.toFixed(1)} />
      <Row
        label="MACD (hist)"
        value={`${ind.macd.macd.toFixed(3)} (${ind.macd.histogram.toFixed(3)})`}
      />
      <Row
        label="Bollinger %B"
        value={`${(ind.bollinger.pct_b * 100).toFixed(0)}%`}
      />
      <Row label="Annualized vol" value={pct(ind.annualized_volatility)} />
    </div>
  );
}
