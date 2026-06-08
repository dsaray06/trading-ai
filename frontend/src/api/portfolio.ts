// Portfolio API calls (all require auth via the interceptor).
import { api } from "@/api/client";
import type {
  Portfolio,
  PortfolioSummary,
  Position,
  ReviewResponse,
  Trade,
} from "@/types/portfolio";

export async function listPortfolios(): Promise<Portfolio[]> {
  return (await api.get<Portfolio[]>("/portfolios")).data;
}

export async function createPortfolio(
  name: string,
  starting_cash: number,
  broker: "simulated" | "alpaca" = "simulated",
): Promise<Portfolio> {
  return (await api.post<Portfolio>("/portfolios", { name, starting_cash, broker }))
    .data;
}

export async function getSummary(id: string): Promise<PortfolioSummary> {
  return (await api.get<PortfolioSummary>(`/portfolios/${id}`)).data;
}

export async function getPositions(id: string): Promise<Position[]> {
  return (await api.get<Position[]>(`/portfolios/${id}/positions`)).data;
}

export async function getTrades(id: string): Promise<Trade[]> {
  return (await api.get<Trade[]>(`/portfolios/${id}/trades`)).data;
}

export async function acceptTrade(
  id: string,
  recommendation_id: string,
  quantity?: number,
): Promise<Trade> {
  return (
    await api.post<Trade>(`/portfolios/${id}/trades`, {
      recommendation_id,
      quantity,
    })
  ).data;
}

export async function reviewPortfolio(id: string): Promise<ReviewResponse> {
  return (await api.post<ReviewResponse>(`/portfolios/${id}/review`)).data;
}
