import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Map, Plus, Trash2, RefreshCcw, AlertCircle, Navigation } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface Point {
  name: string;
  lat?: number | null;
  lon?: number | null;
}

interface RouteOptimizerBoxProps {
  points?: Point[];
  destinationName?: string;
}

export const RouteOptimizerBox = ({
  points: initialPoints = [],
  destinationName,
}: RouteOptimizerBoxProps) => {
  const [stops, setStops] = useState<Point[]>([]);
  const [newStopName, setNewStopName] = useState("");
  const [route, setRoute] = useState<any[]>([]);
  const [summary, setSummary] = useState<string | null>(null);
  const [totalKm, setTotalKm] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialPoints && initialPoints.length > 0) {
      setStops(initialPoints);
    } else if (destinationName) {
      setStops([{ name: destinationName }]);
    }
  }, [initialPoints, destinationName]);

  const addStop = () => {
    if (!newStopName.trim()) return;
    setStops([...stops, { name: newStopName.trim() }]);
    setNewStopName("");
    setRoute([]);
    setSummary(null);
  };

  const removeStop = (idx: number) => {
    const updated = stops.filter((_, i) => i !== idx);
    setStops(updated);
    setRoute([]);
    setSummary(null);
  };

  const optimize = async () => {
    if (stops.length === 0) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("http://127.0.0.1:8000/routes/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          points: stops,
          destination_name: destinationName,
        }),
      });

      if (!res.ok) {
        throw new Error(`Route optimization failed (${res.status})`);
      }

      const data = await res.json();
      setRoute(data.ordered_points || []);
      setSummary(data.summary || null);
      setTotalKm(data.total_distance_km ?? null);
    } catch (err: any) {
      console.error("Route error:", err);
      setError("Failed to optimize route. Please check connection and retry.");
      setRoute([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
            <Map className="h-5 w-5 text-coral" />
            <span>AI Route Optimizer</span>
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Optimize visiting order using nearest-neighbor heuristic to minimize travel distance.
          </p>
        </div>

        <Button
          onClick={optimize}
          disabled={loading || stops.length === 0}
          size="sm"
          className="text-xs h-8"
        >
          {loading ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
              Optimizing...
            </>
          ) : (
            "Optimize Route"
          )}
        </Button>
      </div>

      {/* Stops list & adding stop */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          <Input
            placeholder="Add stop (e.g. Airport, Hotel, Old Market)..."
            value={newStopName}
            onChange={(e) => setNewStopName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addStop()}
            className="text-xs h-9 flex-1 min-w-[200px]"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addStop}
            className="text-xs h-9"
          >
            <Plus className="h-3.5 w-3.5 mr-1" /> Add Stop
          </Button>
        </div>

        <div className="flex flex-wrap gap-2 pt-1">
          {stops.map((s, idx) => (
            <Badge
              key={idx}
              variant="secondary"
              className="text-xs py-1 px-2.5 flex items-center gap-1.5 bg-muted/60"
            >
              <span className="font-semibold text-primary">{idx + 1}.</span>
              <span>{s.name}</span>
              {stops.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeStop(idx)}
                  className="hover:text-red-500 transition-colors ml-1"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              )}
            </Badge>
          ))}
        </div>
      </div>

      {error && (
        <div className="flex items-center justify-between rounded-xl bg-destructive/10 text-destructive text-xs p-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={optimize}
            className="text-xs h-7 px-2"
          >
            <RefreshCcw className="h-3 w-3 mr-1" /> Retry
          </Button>
        </div>
      )}

      {loading && (
        <div className="py-6 flex items-center justify-center text-xs text-muted-foreground gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <span>Computing distance matrix and 2-opt sequence...</span>
        </div>
      )}

      {/* Optimized Output */}
      {!loading && route.length > 0 && (
        <div className="space-y-3 pt-2">
          {summary && (
            <div className="p-3 bg-primary/5 rounded-xl border border-primary/20 text-xs text-foreground font-medium flex items-center justify-between">
              <span>{summary}</span>
              {totalKm !== null && (
                <Badge variant="default" className="text-xs shrink-0">
                  {totalKm.toFixed(1)} km
                </Badge>
              )}
            </div>
          )}

          <div className="space-y-2">
            {route.map((p, i) => (
              <div
                key={i}
                className="p-3 bg-muted/40 rounded-xl border border-border/40 text-xs flex items-center justify-between text-foreground"
              >
                <div className="flex items-center gap-2.5">
                  <div className="h-6 w-6 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center text-[11px] shrink-0">
                    {i + 1}
                  </div>
                  <span className="font-medium">{p.name}</span>
                </div>
                {p.lat && p.lon ? (
                  <span className="text-[11px] text-muted-foreground font-mono">
                    {Number(p.lat).toFixed(4)}, {Number(p.lon).toFixed(4)}
                  </span>
                ) : (
                  <span className="text-[10px] text-muted-foreground italic">
                    Resolved by name
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && !error && route.length === 0 && (
        <p className="text-xs text-muted-foreground italic py-1">
          {stops.length < 2
            ? "Add your arrival point (e.g. airport or hotel) above and click 'Optimize Route' to find the shortest visiting order."
            : "Click 'Optimize Route' to compute the shortest path sequence for your stops."}
        </p>
      )}
    </div>
  );
};
