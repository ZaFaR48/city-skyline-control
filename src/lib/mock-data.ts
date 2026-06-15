export type StationStatus = "online" | "warning" | "offline";

export interface Station {
  id: string;
  name: string;
  region: string;
  address: string;
  vpnIp: string;
  localIp: string;
  status: StationStatus;
  ping: number; // ms
  packetLoss: number; // %
  cpu: number; // %
  ram: number; // %
  disk: number; // %
  lastSeen: string; // ISO
  rustdeskId: string;
  lat: number;
  lng: number;
  cameras: number;
}

export interface Camera {
  id: string;
  name: string;
  stationId: string;
  stationName: string;
  ip: string;
  rtsp: string;
  status: StationStatus;
  ptz: boolean;
  resolution: string;
  fps: number;
}

export type AlertSeverity = "critical" | "warning" | "info";
export type AlertType =
  | "offline_station"
  | "camera_offline"
  | "vpn_lost"
  | "disk_full"
  | "cpu_high"
  | "ram_high";

export interface AlertItem {
  id: string;
  type: AlertType;
  severity: AlertSeverity;
  station: string;
  message: string;
  createdAt: string;
  acknowledged: boolean;
}

const REGIONS = [
  { name: "Dushanbe", lat: 38.5598, lng: 68.787 },
  { name: "Khujand", lat: 40.2833, lng: 69.6333 },
  { name: "Bokhtar", lat: 37.8333, lng: 68.7833 },
  { name: "Kulob", lat: 37.9167, lng: 69.7833 },
  { name: "Khorog", lat: 37.4833, lng: 71.55 },
  { name: "Istaravshan", lat: 39.9167, lng: 69.0167 },
  { name: "Tursunzoda", lat: 38.5108, lng: 68.2289 },
  { name: "Panjakent", lat: 39.4936, lng: 67.6131 },
  { name: "Vahdat", lat: 38.5667, lng: 69.0167 },
  { name: "Hisor", lat: 38.5256, lng: 68.5439 },
];

const STREETS = [
  "Rudaki Ave", "Ismoili Somoni St", "Aini St", "Firdavsi St",
  "Lohuti St", "Bukhoro St", "Navoi St", "Tursunzoda St",
];

function seeded(i: number) {
  // deterministic-ish pseudo random
  const x = Math.sin(i * 9301 + 49297) * 233280;
  return x - Math.floor(x);
}

function pick<T>(arr: T[], i: number): T {
  return arr[Math.floor(seeded(i) * arr.length)];
}

function jitter(base: number, range: number, seed: number) {
  return base + (seeded(seed) - 0.5) * range;
}

export function generateStations(count = 42): Station[] {
  const now = Date.now();
  return Array.from({ length: count }, (_, i) => {
    const region = REGIONS[i % REGIONS.length];
    const r = seeded(i + 1);
    const status: StationStatus =
      r > 0.88 ? "offline" : r > 0.78 ? "warning" : "online";
    const ping = status === "offline" ? 0 : Math.round(jitter(60, 180, i + 7));
    const idx = String(i + 1).padStart(2, "0");
    return {
      id: `STN-${idx}`,
      name: `${region.name}-${idx}`,
      region: region.name,
      address: `${pick(STREETS, i + 2)} ${Math.floor(seeded(i + 5) * 200) + 1}`,
      vpnIp: `100.64.${Math.floor(i / 254)}.${(i % 254) + 1}`,
      localIp: `10.${10 + (i % 5)}.${Math.floor(i / 10)}.${(i % 50) + 10}`,
      status,
      ping: Math.max(0, ping),
      packetLoss: status === "offline" ? 100 : Math.round(seeded(i + 11) * 5),
      cpu: Math.round(jitter(45, 50, i + 13)),
      ram: Math.round(jitter(55, 40, i + 17)),
      disk: Math.round(jitter(60, 35, i + 19)),
      lastSeen: new Date(
        now - Math.floor(seeded(i + 23) * (status === "offline" ? 3600_000 * 6 : 120_000))
      ).toISOString(),
      rustdeskId: `${100000000 + i * 137}`,
      lat: jitter(region.lat, 0.04, i + 29),
      lng: jitter(region.lng, 0.06, i + 31),
      cameras: 2 + Math.floor(seeded(i + 37) * 4),
    };
  });
}

export function generateCameras(stations: Station[]): Camera[] {
  const cams: Camera[] = [];
  stations.forEach((s, si) => {
    for (let c = 0; c < s.cameras; c++) {
      const r = seeded(si * 7 + c);
      const status: StationStatus =
        s.status === "offline"
          ? "offline"
          : r > 0.9
          ? "offline"
          : r > 0.82
          ? "warning"
          : "online";
      cams.push({
        id: `${s.id}-CAM${c + 1}`,
        name: `${s.name} • Cam ${c + 1}`,
        stationId: s.id,
        stationName: s.name,
        ip: `${s.localIp.split(".").slice(0, 3).join(".")}.${100 + c}`,
        rtsp: `rtsp://admin:••••@${s.localIp.split(".").slice(0, 3).join(".")}.${100 + c}:554/Streaming/Channels/${c + 1}01`,
        status,
        ptz: c === 0,
        resolution: c === 0 ? "1920x1080" : "1280x720",
        fps: c === 0 ? 25 : 15,
      });
    }
  });
  return cams;
}

export function generateAlerts(stations: Station[], cameras: Camera[]): AlertItem[] {
  const alerts: AlertItem[] = [];
  const now = Date.now();
  stations.forEach((s, i) => {
    if (s.status === "offline") {
      alerts.push({
        id: `A-${s.id}-OFF`,
        type: "offline_station",
        severity: "critical",
        station: s.name,
        message: `Station ${s.name} unreachable on VPN ${s.vpnIp}`,
        createdAt: new Date(now - Math.floor(seeded(i + 41) * 3600_000)).toISOString(),
        acknowledged: false,
      });
    }
    if (s.cpu > 85) {
      alerts.push({
        id: `A-${s.id}-CPU`,
        type: "cpu_high",
        severity: "warning",
        station: s.name,
        message: `CPU usage at ${s.cpu}%`,
        createdAt: new Date(now - Math.floor(seeded(i + 43) * 1800_000)).toISOString(),
        acknowledged: false,
      });
    }
    if (s.ram > 85) {
      alerts.push({
        id: `A-${s.id}-RAM`,
        type: "ram_high",
        severity: "warning",
        station: s.name,
        message: `RAM usage at ${s.ram}%`,
        createdAt: new Date(now - Math.floor(seeded(i + 47) * 1800_000)).toISOString(),
        acknowledged: false,
      });
    }
    if (s.disk > 90) {
      alerts.push({
        id: `A-${s.id}-DISK`,
        type: "disk_full",
        severity: "critical",
        station: s.name,
        message: `Disk usage at ${s.disk}%`,
        createdAt: new Date(now - Math.floor(seeded(i + 53) * 5400_000)).toISOString(),
        acknowledged: false,
      });
    }
  });
  cameras.forEach((c, i) => {
    if (c.status === "offline") {
      alerts.push({
        id: `A-${c.id}`,
        type: "camera_offline",
        severity: "warning",
        station: c.stationName,
        message: `Camera ${c.name} offline (${c.ip})`,
        createdAt: new Date(now - Math.floor(seeded(i + 59) * 2400_000)).toISOString(),
        acknowledged: false,
      });
    }
  });
  return alerts.sort((a, b) => +new Date(b.createdAt) - +new Date(a.createdAt));
}

// Lazy singleton so the same dataset is shared across pages.
let _stations: Station[] | null = null;
let _cameras: Camera[] | null = null;
let _alerts: AlertItem[] | null = null;

export function getDataset() {
  if (!_stations) {
    _stations = generateStations(42);
    _cameras = generateCameras(_stations);
    _alerts = generateAlerts(_stations, _cameras);
  }
  return { stations: _stations!, cameras: _cameras!, alerts: _alerts! };
}

export function liveTick() {
  // Mutate a few metrics in place to simulate realtime updates.
  const { stations } = getDataset();
  stations.forEach((s, i) => {
    if (s.status === "offline") return;
    const drift = (Math.random() - 0.5) * 6;
    s.cpu = Math.max(5, Math.min(99, Math.round(s.cpu + drift)));
    s.ram = Math.max(10, Math.min(99, Math.round(s.ram + drift / 1.5)));
    s.ping = Math.max(8, Math.round(s.ping + (Math.random() - 0.5) * 20));
    s.lastSeen = new Date().toISOString();
    if (s.cpu > 90 || s.ram > 92) s.status = "warning";
    else if (s.cpu < 80 && s.ram < 80) s.status = i % 13 === 0 ? "warning" : "online";
  });
}
