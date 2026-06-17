"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type { Feature, LineString } from "geojson";
import { MapPin } from "lucide-react";
import * as React from "react";

import { type MapPoint, collectMapPoints } from "@/lib/map";
import type { RunRecord } from "@/lib/types";

// Keyless vector tiles + style (no API key, consistent with the OSS tool stack).
const STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";
const CITY_COLOR = "#ef6c4d"; // brand coral
const POI_COLOR = "#1f9fb0"; // ocean teal

function lineFeature(centers: MapPoint[]): Feature<LineString> {
  return {
    type: "Feature",
    properties: {},
    geometry: { type: "LineString", coordinates: centers.map((c) => [c.lng, c.lat]) },
  };
}

export function MapView({ record }: { record: RunRecord }) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const { points, cityCenters } = React.useMemo(() => collectMapPoints(record), [record]);

  React.useEffect(() => {
    const container = containerRef.current;
    if (!container || points.length === 0) return;

    let cancelled = false;
    let map: import("maplibre-gl").Map | null = null;

    (async () => {
      const maplibregl = (await import("maplibre-gl")).default;
      if (cancelled || !container) return;

      map = new maplibregl.Map({
        container,
        style: STYLE_URL,
        center: [points[0].lng, points[0].lat],
        zoom: 10,
        attributionControl: { compact: true },
      });
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

      const bounds = new maplibregl.LngLatBounds();
      for (const p of points) {
        new maplibregl.Marker({ color: p.kind === "city" ? CITY_COLOR : POI_COLOR })
          .setLngLat([p.lng, p.lat])
          .setPopup(new maplibregl.Popup({ offset: 24 }).setText(p.name))
          .addTo(map);
        bounds.extend([p.lng, p.lat]);
      }

      map.on("load", () => {
        if (!map) return;
        if (cityCenters.length > 1) {
          map.addSource("legs", { type: "geojson", data: lineFeature(cityCenters) });
          map.addLayer({
            id: "legs-line",
            type: "line",
            source: "legs",
            layout: { "line-cap": "round", "line-join": "round" },
            paint: { "line-color": CITY_COLOR, "line-width": 3, "line-dasharray": [2, 1.5] },
          });
        }
        if (!bounds.isEmpty()) {
          map.fitBounds(bounds, { padding: 56, maxZoom: 14, duration: 0 });
        }
      });
    })();

    return () => {
      cancelled = true;
      if (map) map.remove();
    };
  }, [points, cityCenters]);

  if (points.length === 0) return null;

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <h2 className="flex items-center gap-2 font-semibold">
          <MapPin className="size-4 text-primary" /> Map
        </h2>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="size-2.5 rounded-full" style={{ background: CITY_COLOR }} /> City
          </span>
          <span className="flex items-center gap-1">
            <span className="size-2.5 rounded-full" style={{ background: POI_COLOR }} /> Place
          </span>
        </div>
      </div>
      <div ref={containerRef} className="h-[420px] w-full" />
    </div>
  );
}
