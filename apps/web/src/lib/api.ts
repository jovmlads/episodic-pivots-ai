/**
 * Typed client for the FastAPI backend.
 * All requests include X-User-Id header set server-side.
 */
import type { ScreenerConfig, ScanRun, ScanResult, AIAnalysis } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(
  path: string,
  options: RequestInit & { userId?: string } = {}
): Promise<T> {
  const { userId, ...init } = options;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  if (userId) headers["X-User-Id"] = userId;

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

// ── Screener configs ──────────────────────────────────────────────────────────

export const api = {
  configs: {
    list: (userId: string) =>
      apiFetch<ScreenerConfig[]>("/configs", { userId }),

    create: (userId: string, body: Partial<ScreenerConfig>) =>
      apiFetch<ScreenerConfig>("/configs", {
        method: "POST",
        body: JSON.stringify(body),
        userId,
      }),

    update: (userId: string, id: string, body: Partial<ScreenerConfig>) =>
      apiFetch<ScreenerConfig>(`/configs/${id}`, {
        method: "PUT",
        body: JSON.stringify(body),
        userId,
      }),

    delete: (userId: string, id: string) =>
      apiFetch<void>(`/configs/${id}`, { method: "DELETE", userId }),
  },

  scans: {
    list: (userId: string, limit = 20) =>
      apiFetch<ScanRun[]>(`/scans?limit=${limit}`, { userId }),

    get: (userId: string, runId: string) =>
      apiFetch<{ run: ScanRun; results: ScanResult[] }>(`/scans/${runId}`, { userId }),
  },

  analyses: {
    list: (userId: string, limit = 50, offset = 0) =>
      apiFetch<AIAnalysis[]>(`/analyses?limit=${limit}&offset=${offset}`, { userId }),

    similar: (userId: string, resultId: string, limit = 5) =>
      apiFetch<AIAnalysis[]>(`/analyses/similar?result_id=${resultId}&limit=${limit}`, { userId }),
  },
};

// SSE trigger — returns EventSource-compatible URL
export function scanStreamUrl(configId: string): string {
  return `/api/scans/stream?config_id=${configId}`;
}
