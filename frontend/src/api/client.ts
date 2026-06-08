// Axios client + typed API calls. Base URL comes from VITE_API_BASE_URL.
import axios from "axios";
import { getToken } from "@/auth/token";
import type { AssetType, Recommendation } from "@/types/research";

// Accept a full URL or a bare host (Render injects the backend host without a
// scheme); fall back to local dev.
function resolveBaseUrl(value: string | undefined): string {
  if (!value) return "http://localhost:8000";
  return value.startsWith("http") ? value : `https://${value}`;
}

const baseURL = resolveBaseUrl(import.meta.env.VITE_API_BASE_URL);

export const api = axios.create({ baseURL, timeout: 60_000 });

// Attach the JWT (if any) to every request.
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    return (
      (err.response?.data as { detail?: string } | undefined)?.detail ?? err.message
    );
  }
  return fallback;
}

export interface ResearchRequest {
  asset_type?: AssetType;
  horizon?: "short" | "medium" | "long";
  include_options?: boolean;
}

export async function researchTicker(
  ticker: string,
  body: ResearchRequest = {},
): Promise<Recommendation> {
  const res = await api.post<Recommendation>(
    `/research/${encodeURIComponent(ticker)}`,
    body,
  );
  return res.data;
}
