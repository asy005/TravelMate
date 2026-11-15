import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, Sparkles, RefreshCcw, AlertCircle } from "lucide-react";
import { getHighlights } from "@/lib/api";

interface HighlightsBoxProps {
  destination?: any;
  query?: string;
}

export const HighlightsBox = ({ destination, query }: HighlightsBoxProps) => {
  const [highlights, setHighlights] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasGenerated, setHasGenerated] = useState(false);

  const targetQuery =
    (typeof destination === "string" ? destination : destination?.name) || query || "";
  const destId = typeof destination === "object" ? destination?.id || destination?.csv_destination_id : undefined;

  useEffect(() => {
    setHighlights([]);
    setError(null);
    setHasGenerated(false);
  }, [destination?.id, destination?.name, query]);

  const fetchHighlights = async () => {
    if (!targetQuery) return;
    setLoading(true);
    setError(null);
    setHasGenerated(true);

    try {
      const data = await getHighlights(targetQuery, targetQuery, destId);
      let list = data.highlights || [];

      // If backend returned empty but destination has verified attractions on frontend
      if (list.length === 0 && Array.isArray(destination?.attractions) && destination.attractions.length > 0) {
        list = destination.attractions.slice(0, 4).map((att: any) => {
          const cat = att.category ? `— ${att.category}` : "";
          const rating = att.rating ? ` (${att.rating}★)` : "";
          const fee = att.entry_fee === 0 ? " • Free entry" : (att.entry_fee ? ` • Entry ₹${att.entry_fee}` : "");
          return `${att.name} ${cat}${rating}${fee} in ${att.city || targetQuery}.`;
        });
      }

      setHighlights(list);
    } catch (err: any) {
      console.error("Highlights error:", err);
      // Graceful fallback from client-side verified attractions if API fails
      if (Array.isArray(destination?.attractions) && destination.attractions.length > 0) {
        const list = destination.attractions.slice(0, 4).map((att: any) => {
          const cat = att.category ? `— ${att.category}` : "";
          const rating = att.rating ? ` (${att.rating}★)` : "";
          const fee = att.entry_fee === 0 ? " • Free entry" : (att.entry_fee ? ` • Entry ₹${att.entry_fee}` : "");
          return `${att.name} ${cat}${rating}${fee} in ${att.city || targetQuery}.`;
        });
        setHighlights(list);
      } else {
        setError("Unable to load destination highlights. Click retry to try again.");
        setHighlights([]);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
          <Sparkles className="h-5 w-5 text-amber-500" />
          <span>Top Highlights</span>
        </h2>

        <Button
          onClick={fetchHighlights}
          disabled={loading || !targetQuery}
          size="sm"
          className="text-xs h-8"
        >
          {loading ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
              Generating...
            </>
          ) : (
            "Generate Highlights"
          )}
        </Button>
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
            onClick={fetchHighlights}
            className="text-xs h-7 px-2"
          >
            <RefreshCcw className="h-3 w-3 mr-1" /> Retry
          </Button>
        </div>
      )}

      {loading && (
        <div className="py-6 flex items-center justify-center text-xs text-muted-foreground gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <span>Extracting verified attraction highlights for {targetQuery}...</span>
        </div>
      )}

      {!loading && highlights.length > 0 && (
        <ul className="space-y-2.5">
          {highlights.map((h, i) => (
            <li
              key={i}
              className="p-3.5 bg-muted/40 rounded-xl border border-border/40 text-sm leading-relaxed flex items-start gap-2.5 text-foreground"
            >
              <span className="text-amber-500 font-bold shrink-0">✦</span>
              <span>{h}</span>
            </li>
          ))}
        </ul>
      )}

      {!loading && !error && hasGenerated && highlights.length === 0 && (
        <div className="py-6 px-4 bg-muted/20 border border-dashed border-border rounded-xl text-center space-y-1.5">
          <p className="text-sm font-semibold text-foreground">
            No Verified Attraction Highlights Available
          </p>
          <p className="text-xs text-muted-foreground max-w-md mx-auto">
            No verified attraction records are currently documented for {targetQuery}. Explore regional landmarks or check back as more attractions are added.
          </p>
        </div>
      )}

      {!loading && !error && !hasGenerated && highlights.length === 0 && (
        <p className="text-xs text-muted-foreground italic py-2">
          Click "Generate Highlights" to view curated highlights from verified attraction records for {targetQuery || "this destination"}.
        </p>
      )}
    </div>
  );
};
