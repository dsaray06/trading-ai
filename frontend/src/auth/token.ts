// Tiny JWT storage helper (localStorage). The token is attached to requests by
// the axios interceptor in api/client.ts.
const KEY = "trading-ai-token";

export const getToken = (): string | null => localStorage.getItem(KEY);
export const setToken = (t: string): void => localStorage.setItem(KEY, t);
export const clearToken = (): void => localStorage.removeItem(KEY);
