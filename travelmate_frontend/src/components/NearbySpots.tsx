// src/components/NearbySpots.tsx
import { useState } from "react";

export default function NearbySpots() {
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [spots, setSpots] = useState<any[]>([]);

  const search = async () => {
    const q = await fetch(`http://127.0.0.1:8000/nearby/?lat=${lat}&lon=${lon}`);
    const j = await q.json();
    setSpots(j || []);
  };

  return (
    <div className="p-4">
      <div className="flex gap-2 mb-4">
        <input placeholder="lat" value={lat} onChange={e=>setLat(e.target.value)} className="p-2 border" />
        <input placeholder="lon" value={lon} onChange={e=>setLon(e.target.value)} className="p-2 border" />
        <button onClick={search} className="bg-primary text-white px-3 rounded">Search</button>
      </div>
      <ul>
        {spots.map((s:any, i:number)=>(
          <li key={i} className="mb-2">
            <strong>{s.name || s.kind}</strong> — {s.dist ? Math.round(s.dist) + "m" : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}
