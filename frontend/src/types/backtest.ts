// Types mirroring the backend backtest schemas (docs/05-api-spec.md).

export type Horizon = "1Y" | "3Y" | "5Y" | "10Y";
export type Benchmark = "SPY" | "QQQ" | "VTI" | "custom";

export interface BacktestRequest {
  strategy: string;
  symbol: string;
  benchmark: Benchmark;
  benchmark_symbol?: string;
  horizon: Horizon;
}

export interface EquityPoint {
  date: string;
  strategy: number;
  benchmark: number;
}

export interface BacktestOut {
  id: string;
  strategy: string;
  strategy_label: string;
  symbol: string;
  benchmark: string;
  horizon: string;
  start_date: string;
  end_date: string;
  metrics: Record<string, number>;
  equity_curve: EquityPoint[];
  created_at: string;
}

export interface BacktestSummary {
  id: string;
  strategy: string;
  strategy_label: string;
  symbol: string;
  benchmark: string;
  horizon: string;
  metrics: Record<string, number>;
  created_at: string;
}

export const STRATEGIES: { value: string; label: string }[] = [
  { value: "sma_crossover", label: "SMA 20/50 Crossover" },
  { value: "macd_trend", label: "MACD Trend" },
  { value: "rsi_reversion", label: "RSI Mean Reversion" },
  { value: "buy_and_hold", label: "Buy & Hold" },
];
