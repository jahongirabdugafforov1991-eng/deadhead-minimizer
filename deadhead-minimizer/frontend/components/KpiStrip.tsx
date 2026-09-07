"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface EventsSummary {
  relocations_accepted_today: number;
  deadhead_miles_avoided_today: number;
  revenue_protected_today: number;
}

export default function KpiStrip() {
  const [summary, setSummary] = useState<EventsSummary | null>(null);

  async function loadSummary() {
    try {
      const res = await fetch(`${API_URL}/api/v1/events/summary`);
      if (res.ok) setSummary(await res.json());
    } catch {
      // Silent — KPI strip just stays blank if the backend's briefly unreachable,
      // no need for an alarming error banner over a secondary panel.
    }
  }

  useEffect(() => {
    loadSummary();
    const interval = setInterval(loadSummary, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <div className="text-xs uppercase tracking-wide text-slate-500">Relocations accepted today</div>
        <div className="text-2xl font-semibold text-slate-100 mt-1">
          {summary ? summary.relocations_accepted_today : "—"}
        </div>
      </div>
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <div className="text-xs uppercase tracking-wide text-slate-500">Deadhead miles avoided</div>
        <div className="text-2xl font-semibold text-amber-400 mt-1">
          {summary ? summary.deadhead_miles_avoided_today.toLocaleString() : "—"}
        </div>
      </div>
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <div className="text-xs uppercase tracking-wide text-slate-500">Revenue protected today</div>
        <div className="text-2xl font-semibold text-emerald-400 mt-1">
          {summary ? `$${summary.revenue_protected_today.toLocaleString()}` : "—"}
        </div>
      </div>
    </div>
  );
}
