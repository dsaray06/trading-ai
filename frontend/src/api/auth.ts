// Auth API calls.
import { api } from "@/api/client";

export interface UserOut {
  id: string;
  email: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export async function registerUser(email: string, password: string): Promise<UserOut> {
  return (await api.post<UserOut>("/auth/register", { email, password })).data;
}

export async function loginUser(email: string, password: string): Promise<TokenResponse> {
  return (await api.post<TokenResponse>("/auth/login", { email, password })).data;
}

export async function fetchMe(): Promise<UserOut> {
  return (await api.get<UserOut>("/auth/me")).data;
}
