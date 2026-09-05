"use client";

import { useEffect, useRef } from "react";
import mapboxgl, { Map as MapboxMap, Marker, Popup } from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

import { MarketPoint, ZONE_COLORS } from "@/types/market";

mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";

interface MarketMapProps {
  markets: MarketPoint[];
}

/**
 * Renders each market as a colored circle marker sized by ratio.
 *
 * NOTE: HeatmapLayer.tsx (built earlier) renders true filled polygons per
 * KMA, which is the eventual target once real DAT KMA boundary shapes are
 * available (that's typically paid/licensed data). Until then, this simpler
 * marker-based view shows the same information — hot/dead zones, ratio,
 * rate — without needing polygon geometry. Swapping this out for
 * HeatmapLayer later is a page-level change only.
 */
export default function MarketMap({ markets }: MarketMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapboxMap | null>(null);
  const markersRef = useRef<Marker[]>([]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    mapRef.current = new mapboxgl.Map({
      container: containerRef.current,
      style: "mapbox://styles/mapbox/dark-v11",
      center: [-96.5, 39.5],
      zoom: 3.6,
    });
    mapRef.current.addControl(new mapboxgl.NavigationControl(), "top-right");

    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    markets.forEach((market) => {
      const size = 12 + Math.min(market.load_to_truck_ratio, 6) * 4;
      const el = document.createElement("div");
      el.style.width = `${size}px`;
      el.style.height = `${size}px`;
      el.style.borderRadius = "50%";
      el.style.background = ZONE_COLORS[market.zone_classification];
      el.style.border = "2px solid rgba(255,255,255,0.35)";
      el.style.boxShadow = `0 0 ${size / 2}px ${ZONE_COLORS[market.zone_classification]}`;
      el.style.cursor = "pointer";

      const popup = new mapboxgl.Popup({ offset: 10, closeButton: false }).setHTML(`
        <div style="font-family: system-ui, sans-serif; font-size: 12px; color:#0f172a;">
          <strong>${market.kma_name}</strong><br/>
          Ratio: ${market.load_to_truck_ratio.toFixed(2)}x (${market.zone_classification})<br/>
          Loads: ${market.load_count} · Trucks: ${market.truck_count}<br/>
          ${market.avg_outbound_rpm ? `Avg RPM: $${market.avg_outbound_rpm.toFixed(2)}/mi` : ""}
        </div>
      `);

      const marker = new mapboxgl.Marker(el).setLngLat([market.lon, market.lat]).setPopup(popup).addTo(map);
      markersRef.current.push(marker);
    });
  }, [markets]);

  return <div ref={containerRef} className="h-full w-full rounded-lg" />;
}
