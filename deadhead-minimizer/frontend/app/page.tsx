"use client";

import { useEffect, useState } from "react";
import MarketMap from "@/components/map/MarketMap";
import { MarketPoint } from "@/types/market";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface RelocationOption {
  kma_name: string;
  deadhead_miles: number;
  load_to_truck_ratio: number;
  avg_outbound_rpm: number | null;
  net_rpm_arbitrage: number | null;
  zone_classification: string;
  recommended: boolean;
}

export default function DashboardPage() {
  const [markets, setMarkets] = useState<MarketPoint[]>([]);
  const [loadingMarkets, setLoadingMarkets] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [destination, setDestination] = useState("Atlanta, GA");
  const [currentRpm, setCurrentRpm] = useState("2.20");
  const [options, setOptions] = useState<RelocationOption[]>([]);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [lookupLoading, setLookupLoading] = useState(false);

  async function loadMarkets() {
    try {
      setFetchError(null);
      const res = await fetch(`${API_URL}/api/v1/markets/heatmap?equipment_type=van`);
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      setMarkets(await res.json());
    } catch (e) {
      setFetchError(e instanceof Error ? e.message : "Could not reach the backend");
    } finally {
      setLoadingMarkets(false);
    }
  }

  useEffect(() => {
    loadMarkets();
    const interval = setInterval(loadMarkets, 30000); // refresh every 30s
    return () => clearInterval(interval);
  }, []);

  async function runDeadheadLookup() {
    setLookupLoading(true);
    setLookupError(null);
    setOptions([]);
    try {
      const res = await fetch(`${API_URL}/api/v1/routing/analyze-deadhead`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          destination_query: destination,
          target_delivery_date: new Date().toISOString().slice(0, 10),
          equipment_type: "van",
          radius_miles: 150,
          current_rpm: parseFloat(currentRpm) || null,
          max_results: 5,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server returned ${res.status}`);
      }
      const data = await res.json();
      setOptions(data.options);
    } catch (e) {
      setLookupError(e instanceof Error ? e.message : "Lookup failed");
    } finally {
      setLookupLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <header className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-semibold">Dynamic Deadhead Minimizer</h1>
          <p className="text-sm text-slate-400">Live from {API_URL}</p>
        </div>
        <a
          href="/manual-update-form.html"
          className="text-sm px-4 py-2 rounded-md border border-amber-500 text-amber-400 hover:bg-amber-500/10"
        >
          Update market data
        </a>
      </header>

      {fetchError && (
        <div className="mb-4 rounded-md bg-red-950/60 border border-red-800 px-4 py-2 text-sm text-red-300">
          Could not load market data: {fetchError}. Check NEXT_PUBLIC_API_URL and that the backend is awake.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-5">
        <div className="h-[560px] rounded-lg border border-slate-800 overflow-hidden">
          {loadingMarkets ? (
            <div className="h-full flex items-center justify-center text-slate-500 text-sm">Loading markets…</div>
          ) : (
            <MarketMap markets={markets} />
          )}
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-900 p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300 mb-4">
            Deadhead lookup
          </h2>

          <label className="block text-xs text-slate-400 mb-1">Delivery destination</label>
          <input
            className="w-full mb-3 px-3 py-2 rounded-md bg-slate-800 border border-slate-700 text-sm"
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
          />

          <label className="block text-xs text-slate-400 mb-1">Current load RPM ($/mi)</label>
          <input
            className="w-full mb-4 px-3 py-2 rounded-md bg-slate-800 border border-slate-700 text-sm"
            value={currentRpm}
            onChange={(e) => setCurrentRpm(e.target.value)}
          />

          <button
            onClick={runDeadheadLookup}
            disabled={lookupLoading}
            className="w-full py-2 rounded-md bg-amber-500 text-slate-900 font-medium text-sm disabled:opacity-50"
          >
            {lookupLoading ? "Checking…" : "Find best relocation"}
          </button>

          {lookupError && <p className="mt-3 text-sm text-red-400">{lookupError}</p>}

          <div className="mt-4 space-y-2">
            {options.map((opt) => (
              <div
                key={opt.kma_name}
                className={`rounded-md border px-3 py-2 text-sm ${
                  opt.recommended ? "border-amber-500 bg-amber-500/10" : "border-slate-700 bg-slate-800/50"
                }`}
              >
                <div className="flex justify-between font-medium">
                  <span>{opt.kma_name}</span>
                  <span className="text-amber-400">{opt.deadhead_miles} mi</span>
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  Ratio {opt.load_to_truck_ratio.toFixed(2)}x · {opt.zone_classification}
                  {opt.avg_outbound_rpm ? ` · $${opt.avg_outbound_rpm.toFixed(2)}/mi` : ""}
                  {opt.net_rpm_arbitrage !== null ? ` · net ${opt.net_rpm_arbitrage >= 0 ? "+" : ""}${opt.net_rpm_arbitrage}` : ""}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
