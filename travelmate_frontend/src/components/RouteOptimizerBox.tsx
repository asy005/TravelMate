import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, Map } from "lucide-react";

export const RouteOptimizerBox = ({ points }: { points: any[] }) => {
  const [route, setRoute] = useState<any[]>([]);
  const [summary, setSummary] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const optimize = async () => {
    setLoading(true);

    const res = await fetch("http://127.0.0.1:8000/routes/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ points }),
    });

    const data = await res.json();
    setRoute(data.ordered_points || []);
    setSummary(data.summary || null);
    setLoading(false);
  };

  return (
    <div className="bg-white rounded-xl p-6 shadow-md border">
      <h2 className="text-xl font-semibold mb-3 flex items-center gap-2">
        <Map /> Optimized Route
      </h2>

      <Button onClick={optimize} disabled={loading}>
        {loading ? <Loader2 className="animate-spin" /> : "Optimize Route"}
      </Button>

      {summary && (
        <p className="mt-4 text-lg font-medium">
          {summary}
        </p>
      )}

      <ul className="mt-4 space-y-2">
        {route.map((p, i) => (
          <li key={i} className="p-3 bg-secondary rounded-md">
            📍 {i + 1}. {p.name} ({p.lat}, {p.lon})
          </li>
        ))}
      </ul>
    </div>
  );
};
