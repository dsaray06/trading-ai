// App config / feature flags (public).
import { api } from "@/api/client";

export interface AppConfig {
  alpaca_available: boolean;
  disclaimer: string;
}

export async function getConfig(): Promise<AppConfig> {
  return (await api.get<AppConfig>("/config")).data;
}
