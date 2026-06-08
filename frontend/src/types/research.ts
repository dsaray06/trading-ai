// Shared types for the research API. Mirrors backend RecommendationResponse
// (docs/05-api-spec.md).

export type AssetType = "stock" | "etf" | "option";

export interface AgentVote {
  agent: string;
  action: string;
  score: number;
  weight: number;
  reasoning: string;
}

export interface MacdValues {
  macd: number;
  signal: number;
  histogram: number;
}

export interface BollingerValues {
  lower: number;
  middle: number;
  upper: number;
  pct_b: number;
}

export interface TechnicalIndicators {
  last_price: number;
  sma_20: number;
  sma_50: number | null;
  ema_12: number;
  ema_26: number;
  rsi_14: number;
  macd: MacdValues;
  bollinger: BollingerValues;
  annualized_volatility: number;
}

export interface FundamentalAnalysis {
  fundamental_score: number;
  valuation_score: number;
  quality_score: number;
  financial_health_score: number;
  metrics: Record<string, number>;
}

export interface SentimentAnalysis {
  sentiment_score: number;
  risk_score: number;
  catalyst_score: number;
  catalysts: string[];
  risks: string[];
  news_summary: string;
}

export interface OptionsAnalysis {
  action: string;
  options_score: number;
  strike: number;
  expiration: string;
  premium: number;
  contract_symbol: string;
  stop_loss: number | null;
  take_profit: number | null;
  contracts: number;
  implied_volatility: number | null;
  greeks: Record<string, number>;
  risk_reward: Record<string, number>;
  recommended_contracts: Array<Record<string, unknown>>;
}

export interface AnalysisBundle {
  technical?: TechnicalIndicators;
  fundamental?: FundamentalAnalysis;
  sentiment?: SentimentAnalysis;
  options?: OptionsAnalysis;
}

export interface Recommendation {
  id: string;
  ticker: string;
  asset_type: string;
  action: string;
  entry_target: number | null;
  exit_target: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  position_size: number | null;
  confidence: number;
  thesis: string;
  reasoning_report: string;
  agent_votes: AgentVote[];
  analysis: AnalysisBundle;
  disclaimer: string;
}
