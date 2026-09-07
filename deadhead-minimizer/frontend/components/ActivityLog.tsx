"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface SystemEvent {
  id: string;
  event_type: string;
  message: string;
  created_at: string;
}

const EVENT_COLOR: Record<string, string> = {
  relocation_accepted: "text-emerald-400",
  zone_shift: "text-amber-400",
  dead_zone_warning: "text-red-400",
};

export default function ActivityLog() {
  const [events, setEvents] = useState<SystemEvent[]>([]);

  async function loadEvents() {
    try {
      const res = await fetch(`${API_URL}/api/v1/events/recent?limit=15`);
      if (res.ok) setEvents(await res.json());
    } catch {
      // Same as KpiStrip — a quiet miss here shouldn't alarm the whole dashboard.
    }
  }

  useEffect(() => {
    loadEvents();
    const interval = setInterval(loadEvents, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">System activity log</h3>

      {events.length === 0 && (
        <p className="text-sm text-slate-500">
          No activity yet — accept a relocation or update market data to see events here.
        </p>
      )}

      <div className="space-y-1.5 max-h-52 overflow-y-auto font-mono text-xs">
        {events.map((event) => (
          <div key={event.id} className="flex gap-2">
            <span className="text-slate-600 flex-shrink-0">
              {new Date(event.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
            <span className={EVENT_COLOR[event.event_type] ?? "text-slate-300"}>{event.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
