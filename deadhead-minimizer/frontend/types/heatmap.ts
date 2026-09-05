import type { Feature, FeatureCollection, Polygon } from "geojson";

export type ZoneClassification = "hot" | "balanced" | "soft" | "dead";

export interface KmaZoneProperties {
  kma_code: string;
  kma_name: string;
  zip3: string;
  load_count: number;
  truck_count: number;
  load_to_truck_ratio: number;
  zone_classification: ZoneClassification;
  avg_outbound_rpm: number | null;
}

export type KmaZoneFeature = Feature<Polygon, KmaZoneProperties>;
export type KmaZoneFeatureCollection = FeatureCollection<Polygon, KmaZoneProperties>;

/** Fill color per zone classification — mirrors backend thresholds in kma_heatmap.py */
export const ZONE_COLORS: Record<ZoneClassification, string> = {
  hot: "#8B0000",     // dark red — ratio > 4.0
  balanced: "#F97316", // orange — 2.0–4.0
  soft: "#93C5FD",     // light blue — 1.0–2.0
  dead: "#94A3B8",     // grey — ratio < 1.0
};
