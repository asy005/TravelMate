import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, Sparkles, RefreshCcw, AlertCircle } from "lucide-react";

interface HighlightsBoxProps {
  destination?: any;
  query?: string;
}

export const HighlightsBox = ({ destination, query }: HighlightsBoxProps) => {
  const [highlights, setHighlights] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const targetQuery =
    (typeof destination === "string" ? destination : destination?.name) || query || "";

  useEffect(() => {
    setHighlights([]);
    setError(null);
  }, [destination?.id, destination?.name, query]);

  const fetchHighlights = async () => {
    if (!targetQuery) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(
        `http://127.0.0.1:8000/highlights/?query=${encodeURIComponent(
          targetQuery
        )}&destination=${encodeURIComponent(targetQuery)}`
      );
      if (!res.ok) {
        throw new Error(`Highlights service error (${res.status})`);
      }
      const data = await res.json();
      setHighlights(data.highlights || []);
    } catch (err: any) {
      console.error("Highlights error:", err);
      setError("Unable to load destination highlights. Click retry to try again.");
      setHighlights([]);
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
          <span>Analyzing knowledge base for {targetQuery}...</span>
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

      {!loading && !error && highlights.length === 0 && (
        <p className="text-xs text-muted-foreground italic py-2">
          Click "Generate Highlights" to extract curated cultural and tourist highlights for {targetQuery || "this destination"}.
        </p>
      )}
    </div>
  );
};
