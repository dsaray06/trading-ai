// Types mirroring the backend portfolio schemas (docs/05-api-spec.md).

export interface Portfolio {
  id: string;
  name: string;
  broker: string;
  starting_cash: number;
  cash_balance: number;
  created_at: string;
}

export interface PortfolioSummary {
  id: string;
  name: string;
  cash_balance: number;
  positions_value: number;
  total_value: number;
  total_unrealized_pl: number;
  total_pl: number;
  num_positions: number;
  risk: Record<string, unknown>;
}

export interface Position {
  id: string;
  symbol: string;
  asset_type: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pl: number;
  unrealized_pct: number;
  weight_pct: number;
}

export interface Trade {
  id: string;
  symbol: string;
  asset_type: string;
  side: string;
  quantity: number;
  price: number;
  status: string;
  recommendation_id: string | null;
  executed_at: string;
}

export interface TradePreview {
  side: string;
  symbol: string;
  asset_type: string;
  suggested_quantity: number;
  price: number;
  multiplier: number;
  estimated_cost: number;
  pct_of_portfolio: number;
  cash_balance: number;
  note: string;
}

export interface HoldingReviewItem {
  symbol: string;
  action: string;
  unrealized_pct: number;
  position_risk_score: number;
  concentration_flags: string[];
  rebalancing_suggestions: string[];
  reasoning: string;
}

export interface ReviewResponse {
  portfolio_id: string;
  reviews: HoldingReviewItem[];
  risk: Record<string, unknown>;
}
