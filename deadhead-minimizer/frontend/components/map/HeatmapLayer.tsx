"use client";

import { useEffect, useRef, useState } from "react";
import mapboxgl, { Map as MapboxMap, MapMouseEvent, Popup } from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

import { KmaZoneFeatureCollection, ZONE_COLORS } from "@/types/heatmap";

mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";

const SOURCE_ID = "kma-heatmap-source";
const FILL_LAYER_ID = "kma-heatmap-fill";
const OUTLINE_LAYER_ID = "kma-heatmap-outline";

interface HeatmapLayerProps {
  /** GeoJSON FeatureCollection of KMA polygons with load_to_truck_ratio properties */
  data: KmaZoneFeatureCollection;
  /** Initial map center — defaults to continental US center */
  initialCenter?: [number, number];
  initialZoom?: number;
  /** Fired when the user clicks a KMA polygon — pass kma_code up for detail panels */
  onZoneClick?: (kmaCode: string) => void;
  className?: string;
}

/**
 * Renders a Mapbox GL choropleth of Key Market Areas, colored by load-to-truck
 * ratio (dark red = hot zone, grey/blue = dead zone). Designed to receive
 * fresh GeoJSON on every WebSocket tick from the ingestion layer — `data`
 * updates are diffed via `setData` rather than re-mounting the map.
 */
export default function HeatmapLayer({
  data,
  initialCenter = [-98.5795, 39.8283], // geographic center of the contiguous US
  initialZoom = 4.2,
  onZoneClick,
  className,
}: HeatmapLayerProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapboxMap | null>(null);
  const popupRef = useRef<Popup | null>(null);
  const [isMapReady, setIsMapReady] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // --- Initialize the map once ---
  useEffect(() => {
    if (!mapboxgl.accessToken) {
      setLoadError("Missing NEXT_PUBLIC_MAPBOX_TOKEN environment variable.");
      return;
    }
    if (!mapContainerRef.current || mapRef.current) return;

    const map = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: "mapbox://styles/mapbox/dark-v11",
      center: initialCenter,
      zoom: initialZoom,
      attributionControl: true,
    });

    map.addControl(new mapboxgl.NavigationControl(), "top-right");

    map.on("load", () => {
      mapRef.current = map;
      setIsMapReady(true);
    });

    map.on("error", (e) => {
      // Mapbox surfaces async tile/style errors here rather than throwing
      setLoadError(e.error?.message ?? "Unknown Mapbox error");
    });

    return () => {
      map.remove();
      mapRef.current = null;
      setIsMapReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- init once; center/zoom are initial-only
  }, []);

  // --- Add source/layers once the map is ready, then keep them updated on data changes ---
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapReady) return;

    const existingSource = map.getSource(SOURCE_ID) as mapboxgl.GeoJSONSource | undefined;

    if (existingSource) {
      // Cheap update path — avoids re-adding layers on every WebSocket tick
      existingSource.setData(data as GeoJSON.FeatureCollection);
      return;
    }

    map.addSource(SOURCE_ID, {
      type: "geojson",
      data: data as GeoJSON.FeatureCollection,
    });

    map.addLayer({
      id: FILL_LAYER_ID,
      type: "fill",
      source: SOURCE_ID,
      paint: {
        "fill-color": [
          "match",
          ["get", "zone_classification"],
          "hot", ZONE_COLORS.hot,
          "balanced", ZONE_COLORS.balanced,
          "soft", ZONE_COLORS.soft,
          "dead", ZONE_COLORS.dead,
          /* default */ "#475569",
        ],
        "fill-opacity": [
          "interpolate",
          ["linear"],
          ["get", "load_to_truck_ratio"],
          0, 0.35,
          4, 0.55,
          8, 0.8,
        ],
      },
    });

    map.addLayer({
      id: OUTLINE_LAYER_ID,
      type: "line",
      source: SOURCE_ID,
      paint: {
        "line-color": "#0f172a",
        "line-width": 0.75,
      },
    });

    // --- Hover popup with ratio + rate detail ---
    popupRef.current = new mapboxgl.Popup({
      closeButton: false,
      closeOnClick: false,
    });

    map.on("mousemove", FILL_LAYER_ID, (e: MapMouseEvent) => {
      map.getCanvas().style.cursor = "pointer";
      const feature = e.features?.[0];
      if (!feature || !popupRef.current) return;

      const props = feature.properties as Record<string, unknown>;
      const rpm = typeof props.avg_outbound_rpm === "number" ? `$${props.avg_outbound_rpm.toFixed(2)}/mi` : "N/A";

      popupRef.current
        .setLngLat(e.lngLat)
        .setHTML(
          `<div style="font-family: system-ui, sans-serif; font-size: 12px; color: #0f172a;">
             <strong>${props.kma_name}</strong><br/>
             Ratio: ${Number(props.load_to_truck_ratio).toFixed(2)}<br/>
             Loads: ${props.load_count} · Trucks: ${props.truck_count}<br/>
             Avg outbound RPM: ${rpm}
           </div>`
        )
        .addTo(map);
    });

    map.on("mouseleave", FILL_LAYER_ID, () => {
      map.getCanvas().style.cursor = "";
      popupRef.current?.remove();
    });

    map.on("click", FILL_LAYER_ID, (e: MapMouseEvent) => {
      const feature = e.features?.[0];
      const kmaCode = feature?.properties?.kma_code as string | undefined;
      if (kmaCode && onZoneClick) onZoneClick(kmaCode);
    });
  }, [data, isMapReady, onZoneClick]);

  return (
    <div className={className ?? "relative h-full w-full"}>
      <div ref={mapContainerRef} className="h-full w-full rounded-lg" />

      {loadError && (
        <div className="absolute inset-x-4 top-4 rounded-md bg-red-950/90 px-3 py-2 text-sm text-red-200 shadow-lg">
          Map error: {loadError}
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-4 left-4 rounded-md bg-slate-900/90 px-3 py-2 text-xs text-slate-200 shadow-lg">
        <div className="mb-1 font-semibold">Load-to-Truck Ratio</div>
        {(Object.entries(ZONE_COLORS) as [keyof typeof ZONE_COLORS, string][]).map(([zone, color]) => (
          <div key={zone} className="flex items-center gap-2 py-0.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: color }} />
            <span className="capitalize">{zone}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
