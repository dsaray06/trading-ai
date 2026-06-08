// Per-user Alpaca credential management.
import { api } from "@/api/client";

export interface AlpacaStatus {
  connected: boolean;
  api_key_masked: string | null;
}

export async function getAlpacaStatus(): Promise<AlpacaStatus> {
  return (await api.get<AlpacaStatus>("/alpaca/credentials")).data;
}

export async function connectAlpaca(
  api_key: string,
  api_secret: string,
): Promise<AlpacaStatus> {
  return (
    await api.post<AlpacaStatus>("/alpaca/credentials", { api_key, api_secret })
  ).data;
}

export async function disconnectAlpaca(): Promise<AlpacaStatus> {
  return (await api.delete<AlpacaStatus>("/alpaca/credentials")).data;
}
