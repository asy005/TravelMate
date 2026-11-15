import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Loader2,
  Calendar,
  RefreshCcw,
  AlertCircle,
  Clock,
  Sunrise,
  Sun,
  Sunset,
  MapPin,
} from "lucide-react";
import { generatePlan as apiGeneratePlan } from "@/lib/api";

interface SmartItineraryBoxProps {
  destination?: any;
  initialPlan?: Record<string, string[]> | null;
  initialDays?: number;
  onPlanChange?: (plan: Record<string, string[]>, days: number) => void;
}

export const SmartItineraryBox = ({
  destination,
  initialPlan,
  initialDays,
  onPlanChange,
}: SmartItineraryBoxProps) => {
  const destName =
    typeof destination === "string" ? destination : destination?.name || "";
  const destId =
    typeof destination === "object" ? destination?.id || destination?.csv_destination_id : undefined;

  const [days, setDays] = useState(initialDays || 3);
  const [plan, setPlan] = useState<Record<string, string[]> | null>(initialPlan || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialPlan && Object.keys(initialPlan).length > 0) {
      setPlan(initialPlan);
    }
  }, [initialPlan]);

  useEffect(() => {
    if (initialDays && initialDays > 0) {
      setDays(initialDays);
    }
  }, [initialDays]);

  const handleGenerateItinerary = async () => {
    if (!destName) return;
    setLoading(true);
    setError(null);

    const safeDays = Math.max(1, Math.min(14, Number(days) || 3));

    try {
      const data = await apiGeneratePlan(destName, safeDays, destId);
      if (data && data.plan && Object.keys(data.plan).length > 0) {
        setPlan(data.plan);
        if (onPlanChange) {
          onPlanChange(data.plan, safeDays);
        }
      } else {
        throw new Error("No daily activities returned. Please retry.");
      }
    } catch (err: any) {
      console.error("Itinerary error:", err);
      const msg =
        err?.message ||
        "Unable to generate itinerary at this time. Please check connection and retry.";
      setError(msg);
      setPlan(null);
    } finally {
      setLoading(false);
    }
  };

  const parseActivity = (text: string) => {
    const trimmed = text.trim();
    if (trimmed.toLowerCase().startsWith("morning:")) {
      return {
        period: "Morning",
        icon: <Sunrise className="h-3.5 w-3.5 text-amber-500 shrink-0" />,
        badgeClass: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
        content: trimmed.replace(/^morning:\s*/i, ""),
      };
    }
    if (trimmed.toLowerCase().startsWith("afternoon:")) {
      return {
        period: "Afternoon",
        icon: <Sun className="h-3.5 w-3.5 text-sky-500 shrink-0" />,
        badgeClass: "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20",
        content: trimmed.replace(/^afternoon:\s*/i, ""),
      };
    }
    if (trimmed.toLowerCase().startsWith("evening:")) {
      return {
        period: "Evening",
        icon: <Sunset className="h-3.5 w-3.5 text-purple-500 shrink-0" />,
        badgeClass: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
        content: trimmed.replace(/^evening:\s*/i, ""),
      };
    }
    return {
      period: null,
      icon: <Clock className="h-3.5 w-3.5 text-primary shrink-0" />,
      badgeClass: "bg-muted text-foreground border-border",
      content: trimmed,
    };
  };

  return (
    <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
            <Calendar className="h-5 w-5 text-primary" />
            <span>Smart Day-by-Day Itinerary</span>
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Destination-grounded schedule structured into Morning, Afternoon, and Evening activities.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground font-medium">Days:</span>
            <Input
              type="number"
              min={1}
              max={14}
              className="h-8 w-16 text-xs text-center font-medium"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
            />
          </div>
          <Button
            onClick={handleGenerateItinerary}
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
            onClick={handleGenerateItinerary}
            className="text-xs h-7 px-2"
          >
            <RefreshCcw className="h-3 w-3 mr-1" /> Retry
          </Button>
        </div>
      )}

      {loading && (
        <div className="py-8 flex items-center justify-center text-xs text-muted-foreground gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <span>Generating verified day-by-day plan for {destName}...</span>
        </div>
      )}

      {!loading && plan && Object.keys(plan).length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 pt-1">
          {Object.keys(plan).map((dayKey, idx) => (
            <div
              key={dayKey}
              className="bg-muted/40 rounded-xl p-4 border border-border/50 flex flex-col space-y-3"
            >
              <div className="flex items-center justify-between border-b border-border/40 pb-2">
                <Badge variant="default" className="text-xs font-semibold px-2 py-0.5">
                  Day {idx + 1}
                </Badge>
                <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                  <MapPin className="h-3 w-3 text-coral" /> {destName}
                </span>
              </div>

              <div className="space-y-2 flex-1">
                {plan[dayKey].map((act: string, i: number) => {
                  const { period, icon, badgeClass, content } = parseActivity(act);
                  return (
                    <div
                      key={i}
                      className="p-2.5 rounded-lg bg-background/60 border border-border/40 text-xs space-y-1"
                    >
                      {period && (
                        <div className="flex items-center gap-1.5 mb-1">
                          {icon}
                          <span
                            className={`text-[10px] font-semibold px-1.5 py-0.2 rounded border ${badgeClass}`}
                          >
                            {period}
                          </span>
                        </div>
                      )}
                      <p className="text-foreground/90 leading-relaxed font-normal">
                        {content}
                      </p>
                    </div>
                  );
                })}
              </div>
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
