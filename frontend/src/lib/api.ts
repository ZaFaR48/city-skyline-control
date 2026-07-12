import { clearAuth, getToken, setStoredUser, setToken } from "./auth";
import { apiErrorMessage, currentLanguage } from "./i18n";
import type {
  AlertItem,
  ActionPreview,
  Camera,
  DashboardSummary,
  DistrictAssignment,
  DistrictPreview,
  DuplicateAlertGroup,
  DuplicateVpnGroup,
  HeadscaleApprovalPreview,
  HeadscaleClassificationPreview,
  HeadscaleNode,
  Region,
  PasswordResetPreview,
  OperatorActivity,
  OperatorPresence,
  RegistrationRequest,
  Role,
  Station,
  StationApprovalPreview,
  StationRepairPreview,
  StationLifecyclePreview,
  SuspectedDuplicatePair,
  StationDetail,
  StationList,
  UptimeReportRow,
  User,
  TelegramLinkPreview,
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
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
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
    throw new ApiError(
      apiErrorMessage(currentLanguage(), response.status, message),
      response.status,
    );
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
export const sendPresenceHeartbeat = () =>
  apiFetch<{ last_activity_at: string; source: string; write_performed: boolean }>(
    "/api/activity/heartbeat",
    { method: "POST" },
  );
export const getOperatorPresence = (params: Record<string, string | undefined> = {}) =>
  apiFetch<OperatorPresence[]>(`/api/activity/admin/presence${query(params)}`);
export const getOperatorActivity = (params: Record<string, string | undefined> = {}) =>
  apiFetch<OperatorActivity[]>(`/api/activity/admin/events${query(params)}`);
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
export const getHeadscaleNodes = (
  params: Record<string, string | number | boolean | null | undefined> = {},
) => apiFetch<HeadscaleNode[]>(`/api/headscale/nodes${query(params)}`);
export const syncHeadscale = () =>
  apiFetch<{ added: number }>("/api/headscale/sync", { method: "POST" });
export const previewHeadscaleApproval = (id: number, deviceType: string, stationId?: number) =>
  apiFetch<HeadscaleApprovalPreview>(`/api/headscale/nodes/${id}/approval-preview`, {
    method: "POST",
    body: JSON.stringify({ device_type: deviceType, station_id: stationId ?? null }),
  });
export const approveHeadscaleNode = (
  id: number,
  deviceType: string,
  stationId: number | undefined,
  previewToken: string,
) =>
  apiFetch<HeadscaleNode>(`/api/headscale/nodes/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({
      device_type: deviceType,
      station_id: stationId ?? null,
      preview_token: previewToken,
      confirmation: "APPROVE AND LINK",
    }),
  });
export const rejectHeadscaleNode = (id: number) =>
  apiFetch<HeadscaleNode>(`/api/headscale/nodes/${id}/reject`, { method: "POST" });
export const previewHeadscaleClassification = (
  id: number,
  deviceType: string,
  stationId?: number,
) =>
  apiFetch<HeadscaleClassificationPreview>(`/api/headscale/nodes/${id}/classification-preview`, {
    method: "POST",
    body: JSON.stringify({ device_type: deviceType, station_id: stationId ?? null }),
  });
export const applyHeadscaleClassification = (
  id: number,
  deviceType: string,
  stationId: number | undefined,
  previewToken: string,
  confirmation: string,
) =>
  apiFetch<HeadscaleNode>(`/api/headscale/nodes/${id}/classification`, {
    method: "POST",
    body: JSON.stringify({
      device_type: deviceType,
      station_id: stationId ?? null,
      preview_token: previewToken,
      confirmation,
    }),
  });
export const getUptimeReport = (start: string, end: string, districtId?: number) =>
  apiFetch<UptimeReportRow[]>(
    `/api/reports/uptime${query({ start, end, district_id: districtId })}`,
  );
export const getRegistrations = () => apiFetch<RegistrationRequest[]>("/api/registrations");
export const getUsers = () => apiFetch<User[]>("/api/users");
export const reviewRegistration = (id: number, action: string, role?: Role) =>
  apiFetch<{ status: string }>(`/api/registrations/${id}/review`, {
    method: "POST",
    body: JSON.stringify({ action, role: role ?? null }),
  });
export const previewExistingUserLink = (registrationId: number, userId: number) =>
  apiFetch<TelegramLinkPreview>(`/api/registrations/${registrationId}/link-preview`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId }),
  });
export const linkRegistrationToExistingUser = (
  registrationId: number,
  userId: number,
  previewToken: string,
  confirmation: string,
) =>
  apiFetch<{ status: string; user_id: number; notification_sent: boolean }>(
    `/api/registrations/${registrationId}/link-existing`,
    {
      method: "POST",
      body: JSON.stringify({
        user_id: userId,
        preview_token: previewToken,
        confirmation,
      }),
    },
  );
export const previewTelegramPasswordReset = (registrationId: number) =>
  apiFetch<PasswordResetPreview>(`/api/registrations/${registrationId}/password-reset-preview`, {
    method: "POST",
  });
export const initiateTelegramPasswordReset = (
  registrationId: number,
  previewToken: string,
  confirmation: string,
) =>
  apiFetch<{ status: string; username: string; notification_sent: boolean }>(
    `/api/registrations/${registrationId}/password-reset`,
    {
      method: "POST",
      body: JSON.stringify({ preview_token: previewToken, confirmation }),
    },
  );
export const activateAccount = (code: string, password: string) =>
  apiFetch<{ status: "activated"; username: string; role: Role; is_active: boolean }>(
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

export const getDistrictOnboardingStations = () =>
  apiFetch<Station[]>("/api/onboarding/districts/stations");
export const getStationApprovalInventory = (approval: "pending" | "approved" | "all", q?: string) =>
  apiFetch<Station[]>(`/api/onboarding/stations${query({ approval, q })}`);
export const previewStationApproval = (stationId: number, action: "approve" | "revoke") =>
  apiFetch<StationApprovalPreview>(
    `/api/onboarding/stations/${stationId}/${action === "approve" ? "approval-preview" : "revocation-preview"}`,
    { method: "POST" },
  );
export const applyStationApproval = (
  stationId: number,
  action: "approve" | "revoke",
  previewToken: string,
  confirmation: string,
) =>
  apiFetch<Station>(
    `/api/onboarding/stations/${stationId}/${action === "approve" ? "approve" : "revoke"}`,
    {
      method: "POST",
      body: JSON.stringify({ preview_token: previewToken, confirmation }),
    },
  );
export const previewStationRepair = (stationId: number, changes: Record<string, unknown>) =>
  apiFetch<StationRepairPreview>(`/api/onboarding/stations/${stationId}/repair-preview`, {
    method: "POST",
    body: JSON.stringify(changes),
  });
export const applyStationRepair = (
  stationId: number,
  changes: Record<string, unknown>,
  previewToken: string,
  confirmation: string,
) =>
  apiFetch<Station>(`/api/onboarding/stations/${stationId}/repair`, {
    method: "POST",
    body: JSON.stringify({ ...changes, preview_token: previewToken, confirmation }),
  });
export const getStationInventory = (view: string, q?: string) =>
  apiFetch<Station[]>(`/api/onboarding/station-inventory${query({ view, q })}`);
export const previewStationLifecycle = (stationId: number, action: "archive" | "restore") =>
  apiFetch<StationLifecyclePreview>(`/api/onboarding/stations/${stationId}/${action}-preview`, {
    method: "POST",
  });
export const applyStationLifecycle = (
  stationId: number,
  action: "archive" | "restore",
  previewToken: string,
  confirmation: string,
) =>
  apiFetch<Station>(`/api/onboarding/stations/${stationId}/${action}`, {
    method: "POST",
    body: JSON.stringify({ preview_token: previewToken, confirmation }),
  });
export const getSuspectedDuplicates = () =>
  apiFetch<SuspectedDuplicatePair[]>("/api/onboarding/suspected-duplicates");
export const keepBothSuspectedDuplicates = (leftStationId: number, rightStationId: number) =>
  apiFetch<{ status: string; changed: boolean }>("/api/onboarding/suspected-duplicates/keep-both", {
    method: "POST",
    body: JSON.stringify({ left_station_id: leftStationId, right_station_id: rightStationId }),
  });
export const previewDistrictAssignments = (assignments: DistrictAssignment[]) =>
  apiFetch<DistrictPreview>("/api/onboarding/districts/preview", {
    method: "POST",
    body: JSON.stringify({ assignments }),
  });
export const applyDistrictAssignments = (assignments: DistrictAssignment[], previewToken: string) =>
  apiFetch<{ applied: number; unchanged: number }>("/api/onboarding/districts/apply", {
    method: "POST",
    body: JSON.stringify({
      assignments,
      preview_token: previewToken,
      confirmation: "ASSIGN DISTRICTS",
    }),
  });
export const previewDistrictCsv = (file: File) => {
  const body = new FormData();
  body.append("file", file);
  return apiFetch<DistrictPreview>("/api/onboarding/districts/csv/preview", {
    method: "POST",
    body,
  });
};
export const applyDistrictCsv = (file: File, previewToken: string) => {
  const body = new FormData();
  body.append("file", file);
  body.append("preview_token", previewToken);
  body.append("confirmation", "ASSIGN DISTRICTS");
  return apiFetch<{ applied: number; unchanged: number }>("/api/onboarding/districts/csv/apply", {
    method: "POST",
    body,
  });
};
export const downloadDistrictTemplate = async () => {
  const token = getToken();
  if (!token) throw new ApiError("Authentication required", 401);
  const response = await fetch(`${API_URL}/api/onboarding/districts/template.csv`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new ApiError("CSV template could not be downloaded", response.status);
  return response.blob();
};
export const getDuplicateVpnReport = () =>
  apiFetch<DuplicateVpnGroup[]>("/api/onboarding/duplicate-vpn");
export const getDuplicateAlertReport = () =>
  apiFetch<DuplicateAlertGroup[]>("/api/onboarding/duplicate-alerts");
export const previewDuplicateVpnAction = (data: {
  action: "unlink_node" | "clear_station_vpn" | "select_canonical_node" | "cancel";
  vpn_ip: string;
  station_id?: number;
  node_id?: number;
}) =>
  apiFetch<ActionPreview>("/api/onboarding/duplicate-vpn/action-preview", {
    method: "POST",
    body: JSON.stringify(data),
  });
export const applyDuplicateVpnAction = (
  data: {
    action: "unlink_node" | "clear_station_vpn" | "select_canonical_node" | "cancel";
    vpn_ip: string;
    station_id?: number;
    node_id?: number;
  },
  previewToken: string,
) =>
  apiFetch<{ applied: boolean; description?: string; status?: string }>(
    "/api/onboarding/duplicate-vpn/action-apply",
    {
      method: "POST",
      body: JSON.stringify({
        ...data,
        preview_token: previewToken,
        confirmation: "APPLY VPN ACTION",
      }),
    },
  );
