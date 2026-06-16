import { clearAuth, getToken, setToken } from "./auth";
import type {
  AlertItem, Camera, HeadscaleNode, Station, SummaryOut, User,
} from "./types";

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, "") ||
  "http://localhost:8001";

export class ApiError extends Error {
  status: number;
  data: unknown;
  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body && typeof init.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  headers.set("Accept", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch (e) {
    throw new ApiError((e as Error).message || "Network error", 0);
  }

  if (res.status === 401) {
    clearAuth();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.replace("/login");
    }
    throw new ApiError("Unauthorized", 401);
  }

  const text = await res.text();
  const data = text ? (() => { try { return JSON.parse(text); } catch { return text; } })() : null;

  if (!res.ok) {
    const detail =
      (data && typeof data === "object" && "detail" in (data as Record<string, unknown>))
        ? String((data as Record<string, unknown>).detail)
        : res.statusText;
    throw new ApiError(detail || `HTTP ${res.status}`, res.status, data);
  }
  return data as T;
}

export const api = {
  get:  <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  put:  <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body === undefined ? undefined : JSON.stringify(body) }),
  del:  <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

// ---- Typed endpoints ----
export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const r = await api.post<LoginResponse>("/api/auth/login", { username, password });
  setToken(r.access_token);
  return r;
}

export const Endpoints = {
  me:        () => api.get<User>("/api/auth/me"),
  summary:   () => api.get<SummaryOut>("/api/analytics/summary"),
  stations:  () => api.get<Station[]>("/api/stations"),
  cameras:   () => api.get<Camera[]>("/api/cameras"),
  alerts:    () => api.get<AlertItem[]>("/api/alerts"),
  ackAlert:  (id: number) => api.post<AlertItem>(`/api/alerts/${id}/ack`),
  nodes:     () => api.get<HeadscaleNode[]>("/api/headscale/nodes"),
  syncNodes: () => api.post<{ added: number }>("/api/headscale/sync"),
};
