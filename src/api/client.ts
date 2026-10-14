// This module is the single seam where the frontend meets the backend.
// Every function in the other api/*.ts files calls `request()` below to
// reach the real FastAPI service - no component talks to fetch directly.

export class ApiError extends Error {
  status: number;
  constructor(message: string, status = 403) {
    super(message);
    this.status = status;
  }
}

// Vite exposes import.meta.env.VITE_API_BASE_URL; falls back to same-origin
// /api for a reverse-proxied deployment.
export const BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL || '/api';

const TOKEN_KEY = 'coresight_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export async function request<T>(
  path: string,
  options: { method?: string; body?: unknown } = {}
): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE_URL}${path}`, {
    method: options.method ?? (options.body ? 'POST' : 'GET'),
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!res.ok) {
    let message = res.statusText;
    try {
      const data = await res.json();
      message = data.detail ?? message;
    } catch {
      // response had no JSON body
    }
    throw new ApiError(message, res.status);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
