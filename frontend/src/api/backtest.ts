// Backtest API calls (all require auth via the interceptor).
import { api } from "@/api/client";
import type { BacktestOut, BacktestRequest, BacktestSummary } from "@/types/backtest";

export async function createBacktest(req: BacktestRequest): Promise<BacktestOut> {
  return (await api.post<BacktestOut>("/backtests", req)).data;
}

export async function listBacktests(): Promise<BacktestSummary[]> {
  return (await api.get<BacktestSummary[]>("/backtests")).data;
}

export async function getBacktest(id: string): Promise<BacktestOut> {
  return (await api.get<BacktestOut>(`/backtests/${id}`)).data;
}
