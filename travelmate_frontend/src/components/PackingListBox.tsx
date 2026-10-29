import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Backpack, RefreshCcw, AlertCircle, Check } from "lucide-react";

interface PackingListBoxProps {
  destination?: any;
  weather?: any;
}

export const PackingListBox = ({ destination, weather: propWeather }: PackingListBoxProps) => {
  const destName =
    typeof destination === "string" ? destination : destination?.name || "";

  const [days, setDays] = useState(3);
  const [weatherHint, setWeatherHint] = useState("");
  const [activities, setActivities] = useState("Sightseeing, Dining");
  const [packingList, setPackingList] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initialize weather hint from propWeather if available
  useEffect(() => {
    if (propWeather?.temperature !== undefined) {
      const temp = propWeather.temperature;
      if (temp < 15) setWeatherHint("cold");
      else if (temp > 28) setWeatherHint("hot");
      else setWeatherHint("moderate");
    }
  }, [propWeather]);

  const generateList = async () => {
    if (!destName) return;
    setLoading(true);
    setError(null);

    const body = {
      destination: destName, // String guaranteed
      days: Math.max(1, Number(days) || 3),
      weather: weatherHint.trim() || undefined,
      activities: activities
        ? activities.split(",").map((x) => x.trim()).filter(Boolean)
        : [],
    };

    try {
      const res = await fetch("http://127.0.0.1:8000/packing/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        throw new Error(`Packing service error (${res.status})`);
      }

      const data = await res.json();
      setPackingList(data.packing_list || []);
    } catch (err: any) {
      console.error("Packing error:", err);
      setError("Unable to generate packing list. Please retry.");
      setPackingList([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
          <Backpack className="h-5 w-5 text-coral" />
          <span>Smart Packing List</span>
        </h2>

        <Button
          onClick={generateList}
          disabled={loading || !destName}
          size="sm"
          className="text-xs h-8"
        >
          {loading ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
              Generating...
            </>
          ) : (
            "Generate Packing List"
          )}
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-muted-foreground block mb-1 font-medium">Trip Duration (days)</label>
          <Input
            type="number"
            min={1}
            max={30}
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="text-xs h-9"
            placeholder="Days"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground block mb-1 font-medium">Expected Climate</label>
          <Input
            placeholder="hot, cold, rain, moderate..."
            value={weatherHint}
            onChange={(e) => setWeatherHint(e.target.value)}
            className="text-xs h-9"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground block mb-1 font-medium">Planned Activities</label>
          <Input
            placeholder="hiking, beach, dining..."
            value={activities}
            onChange={(e) => setActivities(e.target.value)}
            className="text-xs h-9"
          />
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
            onClick={generateList}
            className="text-xs h-7 px-2"
          >
            <RefreshCcw className="h-3 w-3 mr-1" /> Retry
          </Button>
        </div>
      )}

      {loading && (
        <div className="py-6 flex items-center justify-center text-xs text-muted-foreground gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <span>Generating custom wardrobe and travel essentials for {destName}...</span>
        </div>
      )}

      {!loading && packingList.length > 0 && (
        <div className="pt-2">
          <p className="text-xs text-muted-foreground mb-2 font-medium">
            Recommended items ({packingList.length}):
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
            {packingList.map((item, i) => (
              <div
                key={i}
                className="bg-muted/40 p-2.5 rounded-xl border border-border/40 text-xs flex items-center gap-2 text-foreground"
              >
                <div className="h-4 w-4 rounded-full bg-primary/10 text-primary flex items-center justify-center shrink-0">
                  <Check className="h-2.5 w-2.5" />
                </div>
                <span>{item}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && !error && packingList.length === 0 && (
        <p className="text-xs text-muted-foreground italic py-1">
          Specify your trip days and activities, then click "Generate Packing List" for personalized recommendations.
        </p>
      )}
    </div>
  );
};
