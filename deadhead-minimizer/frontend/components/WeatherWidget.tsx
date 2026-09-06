"use client";

import { useEffect, useState } from "react";

interface WeatherWidgetProps {
  /** City/place name to look up, e.g. "Atlanta, GA" */
  location: string;
}

interface WeatherData {
  resolvedName: string;
  tempF: number;
  windMph: number;
  conditionText: string;
}

// Minimal subset of WMO weather codes (Open-Meteo's standard) mapped to plain text.
const WMO_CODES: Record<number, string> = {
  0: "Clear sky",
  1: "Mostly clear",
  2: "Partly cloudy",
  3: "Overcast",
  45: "Fog",
  48: "Freezing fog",
  51: "Light drizzle",
  61: "Light rain",
  63: "Rain",
  65: "Heavy rain",
  71: "Light snow",
  73: "Snow",
  75: "Heavy snow",
  80: "Rain showers",
  95: "Thunderstorm",
  96: "Thunderstorm w/ hail",
};

export default function WeatherWidget({ location }: WeatherWidgetProps) {
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!location || location.trim().length < 2) return;

    let cancelled = false;
    async function fetchWeather() {
      setLoading(true);
      setError(null);
      try {
        // Open-Meteo's geocoding API — free, no key, no rate-limit hassle for this scale.
        const geoRes = await fetch(
          `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(location)}&count=1&language=en&format=json`
        );
        const geoData = await geoRes.json();
        const place = geoData?.results?.[0];
        if (!place) throw new Error("Location not found");

        const weatherRes = await fetch(
          `https://api.open-meteo.com/v1/forecast?latitude=${place.latitude}&longitude=${place.longitude}` +
            `&current=temperature_2m,wind_speed_10m,weather_code&temperature_unit=fahrenheit&wind_speed_unit=mph`
        );
        const weatherData = await weatherRes.json();
        const current = weatherData?.current;
        if (!current) throw new Error("No current conditions returned");

        if (!cancelled) {
          setWeather({
            resolvedName: `${place.name}${place.admin1 ? `, ${place.admin1}` : ""}`,
            tempF: Math.round(current.temperature_2m),
            windMph: Math.round(current.wind_speed_10m),
            conditionText: WMO_CODES[current.weather_code] ?? "Conditions unavailable",
          });
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not load weather");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    // Debounce so we don't hit the API on every keystroke as the destination field changes.
    const timeout = setTimeout(fetchWeather, 500);
    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [location]);

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">
        Weather at destination
      </h3>
      {loading && <p className="text-sm text-slate-500">Checking conditions…</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}
      {weather && !loading && (
        <div>
          <div className="text-sm text-slate-400 mb-1">{weather.resolvedName}</div>
          <div className="flex items-baseline gap-3">
            <span className="text-2xl font-semibold text-slate-100">{weather.tempF}°F</span>
            <span className="text-sm text-slate-300">{weather.conditionText}</span>
          </div>
          <div className="text-xs text-slate-500 mt-1">Wind {weather.windMph} mph</div>
        </div>
      )}
    </div>
  );
}
