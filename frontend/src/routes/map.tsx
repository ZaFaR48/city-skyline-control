import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Topbar } from "@/components/Topbar";
import { getStations, type StationApi } from "@/lib/api";

import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";

export const Route = createFileRoute("/map")({
  component: MapPage,
});

function getStatusIcon(status: string) {
  const color =
    status === "online"
      ? "#22c55e"
      : status === "warning"
      ? "#eab308"
      : "#ef4444";

  return L.divIcon({
    className: "",
    html: `<div style="
      width:14px;
      height:14px;
      border-radius:50%;
      background:${color};
      border:2px solid white;
      box-shadow:0 0 8px ${color};
    "></div>`,
    iconSize: [14, 14],
  });
}

function MapPage() {
  const [stations, setStations] = useState<StationApi[]>([]);

  useEffect(() => {
    const token = localStorage.getItem("cpcc.access_token");

    if (!token) {
      console.error("Token not found");
      return;
    }

    getStations(token)
      .then(setStations)
      .catch(console.error);
  }, []);

  return (
    <>
      <Topbar
        title="Map"
        subtitle={`${stations.length} stations loaded`}
      />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="glass rounded-xl overflow-hidden">

          <MapContainer
            center={[38.5598, 68.787]}
            zoom={12}
            style={{ height: "700px", width: "100%" }}
          >
            <TileLayer
              attribution="OpenStreetMap"
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {stations
              .filter(
                (s) =>
                  s.lat &&
                  s.lng &&
                  s.lat !== 0 &&
                  s.lng !== 0
              )
              .map((s) => (
                <Marker
                  key={s.id}
                  position={[s.lat, s.lng]}
                  icon={getStatusIcon(s.status)}
                >
                  <Popup>
                    <b>{s.name}</b>
                    <br />
                    Code: {s.code}
                    <br />
                    Status: {s.status}
                    <br />
                    VPN: {s.vpn_ip || "-"}
                    <br />
                    Address: {s.address || "-"}
                  </Popup>
                </Marker>
              ))}
          </MapContainer>

        </div>
      </div>
    </>
  );
}
