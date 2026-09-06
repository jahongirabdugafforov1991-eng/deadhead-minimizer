import { ZONE_COLORS } from "@/types/market";

const ZONE_LABELS: Record<keyof typeof ZONE_COLORS, string> = {
  hot: "Hot — >4.0x, head here",
  balanced: "Balanced — 2.0–4.0x, healthy",
  soft: "Soft — 1.0–2.0x, worth a look",
  dead: "Dead — <1.0x, avoid sitting here",
};

export default function MapLegend() {
  return (
    <div className="absolute bottom-3 left-3 z-10 rounded-lg bg-slate-900/90 backdrop-blur px-3 py-2.5 text-xs text-slate-200 border border-slate-700 shadow-lg">
      <div className="font-semibold text-slate-300 mb-1.5 tracking-wide uppercase text-[10px]">
        Load-to-Truck Ratio
      </div>
      <div className="space-y-1">
        {(Object.keys(ZONE_COLORS) as (keyof typeof ZONE_COLORS)[]).map((zone) => (
          <div key={zone} className="flex items-center gap-2">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: ZONE_COLORS[zone], boxShadow: `0 0 4px ${ZONE_COLORS[zone]}` }}
            />
            <span>{ZONE_LABELS[zone]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
