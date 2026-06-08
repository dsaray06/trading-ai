// Loads the current user's portfolios and exposes create/refresh.
import { useCallback, useEffect, useState } from "react";
import { apiErrorMessage } from "@/api/client";
import { createPortfolio, listPortfolios } from "@/api/portfolio";
import type { Portfolio } from "@/types/portfolio";

export function usePortfolios() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setPortfolios(await listPortfolios());
      setError(null);
    } catch (err) {
      setError(apiErrorMessage(err, "Could not load portfolios."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const create = useCallback(
    async (name: string, startingCash: number, broker: "simulated" | "alpaca" = "simulated") => {
      const pf = await createPortfolio(name, startingCash, broker);
      await refresh();
      return pf;
    },
    [refresh],
  );

  return { portfolios, loading, error, refresh, create };
}
