export interface MarketPoint {
  kma_code: string;
  kma_name: string;
  zip3: string;
  lat: number;
  lon: number;
  load_count: number;
  truck_count: number;
  load_to_truck_ratio: number;
  avg_outbound_rpm: number | null;
  zone_classification: "hot" | "balanced" | "soft" | "dead";
  updated_at: string;
}

export const ZONE_COLORS: Record<MarketPoint["zone_classification"], string> = {
  hot: "#8B0000",
  balanced: "#F97316",
  soft: "#93C5FD",
  dead: "#94A3B8",
};
