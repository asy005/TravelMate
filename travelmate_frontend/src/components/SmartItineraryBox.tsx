import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Calendar, RefreshCcw, AlertCircle, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface SmartItineraryBoxProps {
  destination?: any;
}

export const SmartItineraryBox = ({ destination }: SmartItineraryBoxProps) => {
  const destName =
    typeof destination === "string" ? destination : destination?.name || "";

  const [days, setDays] = useState(3);
  const [plan, setPlan] = useState<Record<string, string[]> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generatePlan = async () => {
    if (!destName) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("http://127.0.0.1:8000/plan/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          destination: destName, // String guaranteed
          days: Math.max(1, Math.min(14, Number(days) || 3)),
        }),
      });

      if (!res.ok) {
        throw new Error(`Itinerary service error (${res.status})`);
      }

      const data = await res.json();
      setPlan(data.plan || null);
    } catch (err: any) {
      console.error("Itinerary error:", err);
      setError("Unable to generate itinerary. Please retry.");
      setPlan(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
          <Calendar className="h-5 w-5 text-primary" />
          <span>Smart Day-by-Day Itinerary</span>
        </h2>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground font-medium">Days:</span>
            <Input
              type="number"
              min={1}
              max={14}
              className="h-8 w-16 text-xs text-center"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
            />
          </div>
          <Button
            onClick={generatePlan}
            disabled={loading || !destName}
            size="sm"
            className="text-xs h-8"
          >
            {loading ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                Planning...
              </>
            ) : (
              "Generate Itinerary"
            )}
          </Button>
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
            onClick={generatePlan}
            className="text-xs h-7 px-2"
          >
            <RefreshCcw className="h-3 w-3 mr-1" /> Retry
          </Button>
        </div>
      )}

      {loading && (
        <div className="py-8 flex items-center justify-center text-xs text-muted-foreground gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <span>Building optimized daily schedule for {destName}...</span>
        </div>
      )}

      {!loading && plan && Object.keys(plan).length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 pt-2">
          {Object.keys(plan).map((dayKey, idx) => (
            <div
              key={dayKey}
              className="bg-muted/40 rounded-xl p-4 border border-border/50 flex flex-col space-y-2.5"
            >
              <div className="flex items-center justify-between border-b border-border/40 pb-2">
                <Badge variant="default" className="text-xs font-semibold px-2 py-0.5">
                  Day {idx + 1}
                </Badge>
                <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                  <Clock className="h-3 w-3" /> Full Day
                </span>
              </div>
              <ul className="space-y-1.5 flex-1">
                {plan[dayKey].map((act: string, i: number) => (
                  <li
                    key={i}
                    className="text-xs text-foreground/90 leading-relaxed flex items-start gap-1.5"
                  >
                    <span className="text-primary font-bold shrink-0 mt-0.5">•</span>
                    <span>{act}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {!loading && !error && !plan && (
        <p className="text-xs text-muted-foreground italic py-1">
          Select duration in days and click "Generate Itinerary" to create an AI-crafted schedule for {destName || "this trip"}.
        </p>
      )}
    </div>
  );
};
