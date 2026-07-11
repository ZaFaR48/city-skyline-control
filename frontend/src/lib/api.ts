import { clearAuth, getToken, setStoredUser, setToken } from "./auth";
import type {
  AlertItem,
  Camera,
  DashboardSummary,
  HeadscaleNode,
  Region,
  RegistrationRequest,
  Role,
  Station,
  StationDetail,
  StationList,
  UptimeReportRow,
  User,
} from "./types";

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

const API_URL =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ||
  "http://13.140.180.178:8001";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function query(params: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") search.set(key, String(value));
  });
  const value = search.toString();
  return value ? `?${value}` : "";
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  authenticated = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (authenticated) {
    const token = getToken();
    if (!token) throw new ApiError("Authentication required", 401);
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (response.status === 401 && authenticated) clearAuth();
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // Non-JSON error response.
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const data = await apiFetch<LoginResponse>(
    "/api/auth/login",
    {
      method: "POST",
      body: JSON.stringify({ username, password }),
    },
    false,
  );
  setToken(data.access_token);
  const user = await apiFetch<User>("/api/auth/me");
  setStoredUser(user);
  return data;
}

export const getDashboardSummary = () => apiFetch<DashboardSummary>("/api/dashboard/summary");
export const getRegions = (active?: boolean) =>
  apiFetch<Region[]>(`/api/regions${query({ active })}`);
export const getStations = (
  params: Record<string, string | number | boolean | null | undefined> = {},
) => apiFetch<StationList>(`/api/stations${query(params)}`);
export const getStation = (id: number) => apiFetch<StationDetail>(`/api/stations/${id}`);
export const getCameras = () => apiFetch<Camera[]>("/api/cameras");
export const getAlerts = (
  params: Record<string, string | number | boolean | null | undefined> = {},
) => apiFetch<AlertItem[]>(`/api/alerts${query(params)}`);
export const acknowledgeAlert = (id: number) =>
  apiFetch<AlertItem>(`/api/alerts/${id}/ack`, { method: "POST" });
export const getHeadscaleNodes = (pending = false) =>
  apiFetch<HeadscaleNode[]>(`/api/headscale/nodes${pending ? "/pending" : ""}`);
export const syncHeadscale = () =>
  apiFetch<{ added: number }>("/api/headscale/sync", { method: "POST" });
export const approveHeadscaleNode = (id: number, deviceType: string, stationId?: number) =>
  apiFetch<HeadscaleNode>(`/api/headscale/nodes/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ device_type: deviceType, station_id: stationId ?? null }),
  });
export const rejectHeadscaleNode = (id: number) =>
  apiFetch<HeadscaleNode>(`/api/headscale/nodes/${id}/reject`, { method: "POST" });
export const getUptimeReport = (start: string, end: string, districtId?: number) =>
  apiFetch<UptimeReportRow[]>(
    `/api/reports/uptime${query({ start, end, district_id: districtId })}`,
  );
export const getRegistrations = () => apiFetch<RegistrationRequest[]>("/api/registrations");
export const reviewRegistration = (id: number, action: string, role?: Role) =>
  apiFetch<{ status: string }>(`/api/registrations/${id}/review`, {
    method: "POST",
    body: JSON.stringify({ action, role: role ?? null }),
  });
export const activateAccount = (code: string, password: string) =>
  apiFetch<{ status: string; username: string }>(
    "/api/registrations/activate",
    { method: "POST", body: JSON.stringify({ code, password }) },
    false,
  );
export const getRustdeskDevices = () =>
  apiFetch<
    Array<{
      station_code: string;
      station: string;
      district_id: number | null;
      vpn_ip: string | null;
      rustdesk_id: string;
    }>
  >("/api/rustdesk");
