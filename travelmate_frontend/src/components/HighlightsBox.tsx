import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, Sparkles } from "lucide-react";

export const HighlightsBox = ({ query }: { query: string }) => {
  const [highlights, setHighlights] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchHighlights = async () => {
    setLoading(true);

    try {
      const res = await fetch(
        `http://127.0.0.1:8000/highlights?query=${encodeURIComponent(query)}`
      );
      const data = await res.json();
      setHighlights(data.highlights || []);
    } catch {
      setHighlights([]);
    }

    setLoading(false);
  };

  return (
    <div className="bg-white rounded-xl p-6 shadow-md border">
      <h2 className="text-xl font-semibold mb-3 flex items-center gap-2">
        <Sparkles className="text-yellow-500" /> Top Highlights
      </h2>

      <Button onClick={fetchHighlights} disabled={loading}>
        {loading ? <Loader2 className="animate-spin" /> : "Generate Highlights"}
      </Button>

      <ul className="mt-4 space-y-2">
        {highlights.length === 0 && !loading && (
          <p className="text-muted-foreground">No highlights yet.</p>
        )}
        {highlights.map((h, i) => (
          <li key={i} className="p-3 bg-secondary rounded-md">
            ⭐ {h}
          </li>
        ))}
      </ul>
    </div>
  );
};
