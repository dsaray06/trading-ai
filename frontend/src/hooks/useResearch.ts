// Hook that runs a research request and tracks loading/error/result state.
// Agent runs are slow, so loading and error states are first-class.
import axios from "axios";
import { useCallback, useState } from "react";
import { researchTicker } from "@/api/client";
import type { AssetType, Recommendation } from "@/types/research";

interface ResearchState {
  data: Recommendation | null;
  loading: boolean;
  error: string | null;
}

export function useResearch() {
  const [state, setState] = useState<ResearchState>({
    data: null,
    loading: false,
    error: null,
  });

  const run = useCallback(
    async (ticker: string, includeOptions = false, assetType: AssetType = "stock") => {
    const symbol = ticker.trim().toUpperCase();
    if (!symbol) return;
    setState({ data: null, loading: true, error: null });
    try {
      const data = await researchTicker(symbol, {
        include_options: includeOptions,
        asset_type: assetType,
      });
      setState({ data, loading: false, error: null });
    } catch (err) {
      let message = "Something went wrong running research.";
      if (axios.isAxiosError(err)) {
        message =
          (err.response?.data as { detail?: string } | undefined)?.detail ??
          err.message;
      }
      setState({ data: null, loading: false, error: message });
    }
  },
    [],
  );

  return { ...state, run };
}
