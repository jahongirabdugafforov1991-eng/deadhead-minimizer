"use client";

import { useState } from "react";
import { MarketPoint } from "@/types/market";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const EQUIPMENT_OPTIONS = ["van", "reefer", "flatbed", "stepdeck", "power_only"];

interface RowState {
  kma_code: string;
  kma_name: string;
  equipment_type: string;
  loads: string;
  trucks: string;
  rpm: string;
}

interface MarketUpdateModalProps {
  markets: MarketPoint[];
  onClose: () => void;
  onSaved: () => void;
}

interface SaveResult {
  kma_code: string;
  equipment_type: string;
  load_to_truck_ratio: number;
  zone_classification: string;
}

function ratioFor(loads: string, trucks: string): string {
  const l = parseFloat(loads);
  const t = parseFloat(trucks);
  if (!isNaN(l) && !isNaN(t) && t > 0) return (l / t).toFixed(2) + "x";
  return "—";
}

export default function MarketUpdateModal({ markets, onClose, onSaved }: MarketUpdateModalProps) {
  const [rows, setRows] = useState<RowState[]>(() =>
    markets.length > 0
      ? markets.map((m) => ({
          kma_code: m.kma_code,
          kma_name: m.kma_name,
          equipment_type: "van",
          loads: String(m.load_count),
          trucks: String(m.truck_count),
          rpm: m.avg_outbound_rpm !== null ? String(m.avg_outbound_rpm) : "",
        }))
      : [{ kma_code: "", kma_name: "", equipment_type: "van", loads: "", trucks: "", rpm: "" }]
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<SaveResult[]>([]);

  function updateRow(index: number, patch: Partial<RowState>) {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  function addRow() {
    setRows((prev) => [...prev, { kma_code: "", kma_name: "", equipment_type: "van", loads: "", trucks: "", rpm: "" }]);
  }

  function removeRow(index: number) {
    setRows((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSave() {
    setError(null);
    setResults([]);

    const updates: { kma_code: string; equipment_type: string; load_count: number; truck_count: number; avg_outbound_rpm: number | null }[] = [];
    let hasError = false;

    for (const row of rows) {
      const code = row.kma_code.trim().toUpperCase();
      if (!code) continue; // skip rows with no market code
      if (row.loads.trim() === "" && row.trucks.trim() === "") continue; // untouched row

      const load_count = parseInt(row.loads, 10);
      const truck_count = parseInt(row.trucks, 10);
      if (isNaN(load_count) || isNaN(truck_count)) {
        hasError = true;
        continue;
      }
      const avg_outbound_rpm = row.rpm.trim() !== "" ? parseFloat(row.rpm) : null;
      updates.push({ kma_code: code, equipment_type: row.equipment_type, load_count, truck_count, avg_outbound_rpm });
    }

    if (hasError || updates.length === 0) {
      setError("Enter loads and trucks for at least one market before saving.");
      return;
    }

    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/markets/manual-update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ updates }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server returned ${res.status}`);
      }
      const data: SaveResult[] = await res.json();
      setResults(data);
      onSaved(); // tells the dashboard to refetch the map immediately
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 p-4 overflow-y-auto">
      <div className="w-full max-w-4xl bg-slate-900 border border-slate-700 rounded-lg mt-10 mb-10">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <div>
            <h2 className="text-base font-semibold text-slate-100">Update market data</h2>
            <p className="text-xs text-slate-500 mt-0.5">Saves instantly and refreshes the map — no page reload needed.</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200 text-xl leading-none px-2">
            ×
          </button>
        </div>

        <div className="p-5">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500 text-xs uppercase">
                  <th className="pb-2 pr-3">Market</th>
                  <th className="pb-2 pr-3">Equipment</th>
                  <th className="pb-2 pr-3">Loads</th>
                  <th className="pb-2 pr-3">Trucks</th>
                  <th className="pb-2 pr-3">Rate ($/mi)</th>
                  <th className="pb-2 pr-3">Ratio</th>
                  <th className="pb-2"></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i} className="border-t border-slate-800">
                    <td className="py-2 pr-3">
                      <input
                        className="w-20 bg-slate-800 border border-slate-700 rounded px-2 py-1 text-slate-100 font-mono text-xs uppercase"
                        value={row.kma_code}
                        placeholder="ATL"
                        onChange={(e) => updateRow(i, { kma_code: e.target.value })}
                      />
                      {row.kma_name && <div className="text-[10px] text-slate-500 mt-0.5">{row.kma_name}</div>}
                    </td>
                    <td className="py-2 pr-3">
                      <select
                        className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-slate-100 text-xs"
                        value={row.equipment_type}
                        onChange={(e) => updateRow(i, { equipment_type: e.target.value })}
                      >
                        {EQUIPMENT_OPTIONS.map((eq) => (
                          <option key={eq} value={eq}>
                            {eq}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-2 pr-3">
                      <input
                        type="number"
                        className="w-20 bg-slate-800 border border-slate-700 rounded px-2 py-1 text-slate-100 text-xs"
                        value={row.loads}
                        onChange={(e) => updateRow(i, { loads: e.target.value })}
                      />
                    </td>
                    <td className="py-2 pr-3">
                      <input
                        type="number"
                        className="w-20 bg-slate-800 border border-slate-700 rounded px-2 py-1 text-slate-100 text-xs"
                        value={row.trucks}
                        onChange={(e) => updateRow(i, { trucks: e.target.value })}
                      />
                    </td>
                    <td className="py-2 pr-3">
                      <input
                        type="number"
                        step="0.01"
                        className="w-20 bg-slate-800 border border-slate-700 rounded px-2 py-1 text-slate-100 text-xs"
                        value={row.rpm}
                        placeholder="2.30"
                        onChange={(e) => updateRow(i, { rpm: e.target.value })}
                      />
                    </td>
                    <td className="py-2 pr-3 font-mono text-xs text-amber-400">{ratioFor(row.loads, row.trucks)}</td>
                    <td className="py-2">
                      <button onClick={() => removeRow(i)} className="text-slate-500 hover:text-red-400 text-xs">
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button onClick={addRow} className="mt-3 text-xs text-slate-400 border border-dashed border-slate-700 rounded px-3 py-2 w-full hover:bg-slate-800">
            + Add another market
          </button>

          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-5 py-2 rounded-md bg-amber-500 text-slate-900 font-medium text-sm disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save update"}
            </button>
            {error && <span className="text-sm text-red-400">{error}</span>}
            {results.length > 0 && <span className="text-sm text-emerald-400">Saved {results.length} markets.</span>}
          </div>

          {results.length > 0 && (
            <div className="mt-4 space-y-1.5">
              {results.map((r) => (
                <div key={r.kma_code} className="flex justify-between text-xs bg-slate-800/50 border border-slate-700 rounded px-3 py-1.5">
                  <span className="text-slate-300">
                    {r.kma_code} · {r.equipment_type} · ratio {r.load_to_truck_ratio.toFixed(2)}x
                  </span>
                  <span className="text-slate-400">{r.zone_classification}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
