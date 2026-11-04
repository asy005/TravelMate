// src/components/NearbySpots.tsx
import { useState } from "react";
import { getNearbySpots } from "@/lib/api";

export default function NearbySpots() {
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [spots, setSpots] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = async () => {
    if (!lat.trim() || !lon.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const q = await getNearbySpots(lat.trim(), lon.trim());
      if (Array.isArray(q)) {
        setSpots(q);
      } else if (q && typeof q === "object" && q.error) {
        setError(q.error);
        setSpots([]);
      } else {
        setSpots([]);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to fetch nearby spots");
      setSpots([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4">
      <div className="flex gap-2 mb-4">
        <input
          placeholder="lat"
          value={lat}
          onChange={(e) => setLat(e.target.value)}
          className="p-2 border rounded"
        />
        <input
          placeholder="lon"
          value={lon}
          onChange={(e) => setLon(e.target.value)}
          className="p-2 border rounded"
        />
        <button
          onClick={search}
          disabled={loading}
          className="bg-primary text-white px-3 rounded"
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </div>
      {error && <p className="text-sm text-destructive mb-2">{error}</p>}
      <ul>
        {spots.map((s: any, i: number) => (
          <li key={i} className="mb-2">
            <strong>{s.name || s.kind}</strong> — {s.dist ? Math.round(s.dist) + "m" : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}
