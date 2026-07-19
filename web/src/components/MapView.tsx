import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";
import { useEffect } from "react";
import type { ProjectFeature } from "../types";
import { stageColor, STAGE_META, STAGE_ORDER, MAP_CENTER, MAP_ZOOM } from "../theme";

function radiusForScore(score: number | null): number {
  const s = score ?? 0;
  return 5 + (s / 100) * 9; // 5..14 px
}

function FlyToSelected({ feature }: { feature: ProjectFeature | null }) {
  const map = useMap();
  useEffect(() => {
    if (feature) {
      const [lng, lat] = feature.geometry.coordinates;
      map.flyTo([lat, lng], Math.max(map.getZoom(), 13), { duration: 0.6 });
    }
  }, [feature, map]);
  return null;
}

interface Props {
  features: ProjectFeature[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  dark: boolean;
}

export default function MapView({ features, selectedId, onSelect, dark }: Props) {
  const tiles = dark
    ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
  const selected = features.find((f) => f.properties.project_id === selectedId) ?? null;

  return (
    <div className="map-wrap">
      <MapContainer center={MAP_CENTER} zoom={MAP_ZOOM} className="map" preferCanvas>
        <TileLayer
          url={tiles}
          attribution='&copy; OpenStreetMap &copy; CARTO'
          subdomains="abcd"
        />
        <FlyToSelected feature={selected} />
        <MarkerClusterGroup chunkedLoading maxClusterRadius={45}>
          {features.map((f) => {
            const p = f.properties;
            const [lng, lat] = f.geometry.coordinates;
            const isSel = p.project_id === selectedId;
            return (
              <CircleMarker
                key={p.project_id}
                center={[lat, lng]}
                radius={radiusForScore(p.lead_score) + (isSel ? 4 : 0)}
                pathOptions={{
                  color: isSel ? "#0b0b0b" : "#ffffff",
                  weight: isSel ? 3 : 1.5,
                  fillColor: stageColor(p.stage, dark),
                  fillOpacity: p.stage === "completed" || p.stage === "stale_unknown" ? 0.55 : 0.9,
                }}
                eventHandlers={{ click: () => onSelect(p.project_id) }}
              >
                <Tooltip>
                  <strong>{p.promoter_org || p.name || "(unnamed)"}</strong>
                  <br />
                  {STAGE_META[p.stage]?.label} · score {p.lead_score ?? "—"}
                  <br />
                  {p.village}, {p.district}
                </Tooltip>
              </CircleMarker>
            );
          })}
        </MarkerClusterGroup>
      </MapContainer>

      <div className="legend" aria-label="Stage legend">
        <div className="legend-title">Lifecycle stage</div>
        {STAGE_ORDER.map((s) => (
          <div className="legend-row" key={s}>
            <span className="legend-dot" style={{ background: stageColor(s, dark) }} />
            <span>{STAGE_META[s].label}</span>
          </div>
        ))}
        <div className="legend-note">Marker size ∝ lead score</div>
      </div>
    </div>
  );
}
