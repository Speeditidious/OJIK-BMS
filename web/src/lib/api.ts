/**
 * API client for OJIK BMS backend.
 * Handles base URL, authentication headers, and token refresh.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Token storage keys
const ACCESS_TOKEN_KEY = "ojik_access_token";
const REFRESH_TOKEN_KEY = "ojik_refresh_token";

// ── Token management ─────────────────────────────────────────────────────────

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

// ── Request helpers ──────────────────────────────────────────────────────────

type RequestOptions = RequestInit & {
  /** Skip automatic Authorization header injection */
  skipAuth?: boolean;
  /** Skip automatic token refresh on 401 */
  skipRefresh?: boolean;
};

let _refreshPromise: Promise<boolean> | null = null;

export async function refreshTokens(): Promise<boolean> {
  // Deduplicate concurrent refresh calls — reuse the in-flight promise.
  if (_refreshPromise) return _refreshPromise;
  _refreshPromise = _doRefresh().finally(() => {
    _refreshPromise = null;
  });
  return _refreshPromise;
}

async function _doRefresh(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  try {
    const response = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      clearTokens();
      return false;
    }

    const data = await response.json();
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    clearTokens();
    return false;
  }
}

/**
 * Base fetch wrapper that automatically injects Authorization headers
 * and handles 401 errors with token refresh.
 */
export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { skipAuth = false, skipRefresh = false, ...fetchOptions } = options;

  const headers = new Headers(fetchOptions.headers);
  headers.set("Content-Type", "application/json");

  if (!skipAuth) {
    const token = getAccessToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...fetchOptions,
    headers,
  });

  // Attempt token refresh on 401
  if (response.status === 401 && !skipRefresh && !skipAuth) {
    const refreshed = await refreshTokens();
    if (refreshed) {
      // Retry with new token
      return apiFetch<T>(path, { ...options, skipRefresh: true });
    }
    // Token refresh failed — redirect to login
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Authentication required");
  }

  if (!response.ok) {
    let errorMessage = `API error: ${response.status}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail ?? errorMessage;
    } catch {
      // ignore parse errors
    }
    throw new Error(errorMessage);
  }

  // Handle empty responses (204 No Content)
  if (response.status === 204) {
    return null as T;
  }

  return response.json() as Promise<T>;
}

// ── Convenience methods ──────────────────────────────────────────────────────

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    apiFetch<T>(path, { method: "GET", ...options }),

  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, {
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
      ...options,
    }),

  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, {
      method: "PATCH",
      body: body !== undefined ? JSON.stringify(body) : undefined,
      ...options,
    }),

  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, {
      method: "PUT",
      body: body !== undefined ? JSON.stringify(body) : undefined,
      ...options,
    }),

  delete: <T>(path: string, options?: RequestOptions) =>
    apiFetch<T>(path, { method: "DELETE", ...options }),

  /** Multipart form upload — does NOT set Content-Type (browser sets boundary automatically). */
  postForm: <T>(path: string, form: FormData, options?: RequestOptions): Promise<T> => {
    const token = getAccessToken();
    const headers = new Headers();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers,
      body: form,
      ...options,
    }).then(async (res) => {
      if (!res.ok) {
        let msg = `API error: ${res.status}`;
        try { const d = await res.json(); msg = d.detail ?? msg; } catch { /* ignore */ }
        throw new Error(msg);
      }
      return res.json() as Promise<T>;
    });
  },

};
