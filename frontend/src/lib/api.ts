import { setToken } from "./auth";

export interface StationApi {
  id: number;
  code: string;
  name: string;
  region: string;
  address: string;
  vpn_ip: string;
  local_ip: string;
  status: string;
  cpu: number;
  ram: number;
  disk: number;
  last_ping_ms: number;
  last_seen: string | null;
  lat: number;
  lng: number;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

const API_URL = "http://13.140.180.178:8001";

export async function login(
  username: string,
  password: string
): Promise<LoginResponse> {

  const res = await fetch(
    `${API_URL}/api/auth/login`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        password,
      }),
    }
  );

  if (!res.ok) {
    throw new Error("Invalid credentials");
  }

  const data = await res.json();

  setToken(data.access_token);

  return data;
}

export async function getStations(token: string) {
  const res = await fetch(
    `${API_URL}/api/stations`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!res.ok) {
    throw new Error("Failed to load stations");
  }

  return await res.json();
}
