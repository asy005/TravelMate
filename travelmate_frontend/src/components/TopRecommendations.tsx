/**
 * TopRecommendations — renders up to 3 ranked recommendations using the existing recommendation pipeline.
 *
 * Shows ranking, destination name, image/reason, and supported cost information.
 * Selecting an option preserves existing preferences and continues trip planning.
 */
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Sparkles,
  MapPin,
  Calendar,
  Medal,
  Loader2,
  AlertTriangle,
  RotateCcw,
  ArrowRight,
  TrendingUp,
} from "lucide-react";
import { getMLRecommendations, MLRecommendation } from "@/lib/api";

interface Props {
  slots?: Record<string, any>;
  onSelect?: (destinationName: string) => void;
  className?: string;
}

function toMLBudget(budget: any): "Low" | "Medium" | "High" {
  if (!budget) return "Medium";
  const s = String(budget).toLowerCase().replace(/,/g, "").replace(/₹/g, "").trim();
  // Numeric value
  const num = parseFloat(s.replace(/[^0-9.]/g, ""));
  if (!isNaN(num)) {
    if (num <= 15000) return "Low";
    if (num <= 40000) return "Medium";
    return "High";
  }
  if (s === "low" || s === "budget" || s === "cheap") return "Low";
  if (s === "luxury" || s === "high") return "High";
  return "Medium";
}

function toMLCategory(style: any, mood: any, interests: any): string {
  const combined = `${style || ""} ${mood || ""} ${interests || ""}`.toLowerCase();
  if (combined.includes("beach") || combined.includes("coastal") || combined.includes("seaside")) return "Beach";
  if (combined.includes("hill") || combined.includes("mountain")) return "Hill Station";
  if (combined.includes("heritage") || combined.includes("historical") || combined.includes("cultural") || combined.includes("temple")) return "Heritage";
  if (combined.includes("forest") || combined.includes("wildlife") || combined.includes("jungle")) return "Forest";
  if (combined.includes("desert")) return "Desert";
  if (combined.includes("adventure") || combined.includes("trek") || combined.includes("rafting")) return "Adventure";
  if (combined.includes("city") || combined.includes("urban")) return "Urban";
  if (combined.includes("relax") || combined.includes("romantic") || combined.includes("couple")) return "Beach";
  // If no slots collected yet (blank conversation), pick Beach as the universal default
  return "Beach";
}

function currentSeason(startDate?: string): string {
  let month: number;
  if (startDate) {
    try {
      month = new Date(startDate).getMonth() + 1;
    } catch {
      month = new Date().getMonth() + 1;
    }
  } else {
    month = new Date().getMonth() + 1;
  }
  if (month >= 3 && month <= 5) return "summer";
  if (month >= 6 && month <= 9) return "monsoon";
  if (month === 10 || month === 11) return "autumn";
  return "winter";
}

const RANK_BADGES = [
  { rank: 1, label: "#1 Pick", color: "bg-primary text-white" },
  { rank: 2, label: "#2 Pick", color: "bg-slate-700 text-white" },
  { rank: 3, label: "#3 Pick", color: "bg-amber-700 text-white" },
];

const DEFAULT_IMAGE =
  "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&q=80&w=800";

export const TopRecommendations = ({ slots = {}, onSelect, className = "" }: Props) => {
  const navigate = useNavigate();
  const [recs, setRecs] = useState<MLRecommendation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRecs = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getMLRecommendations({
        age: Number(slots.age) || 30,
        travel_style: slots.travel_style || "leisure",
        budget: toMLBudget(slots.budget),
        preferred_category: toMLCategory(slots.travel_style, slots.mood, slots.interests),
        preferred_season: currentSeason(slots.start_date),
        top_k: 3,
      });

      // Deduplicate by destination name; keep up to 3 distinct destinations
      const seen = new Set<string>();
      const unique: MLRecommendation[] = [];
      for (const r of response.recommendations || []) {
        const key = (r.destination_name || "").toLowerCase().trim();
        if (key && !seen.has(key)) {
          seen.add(key);
          unique.push(r);
        }
        if (unique.length >= 3) break;
      }
      setRecs(unique);
    } catch (err: any) {
      setError("Unable to load top recommendations right now.");
      console.warn("[TopRecommendations] fetch error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slots.budget, slots.travel_style, slots.mood, slots.interests, slots.start_date]);

  const handleSelect = (rec: MLRecommendation) => {
    // Preserve recommendations in local storage so details are available
    try {
      const existing = JSON.parse(
        localStorage.getItem("travelmate_recommendations") || '{"destinations":[]}'
      );
      const alreadyIn = (existing.destinations || []).some(
        (d: any) =>
          (d.name || "").toLowerCase() === rec.destination_name.toLowerCase()
      );
      if (!alreadyIn) {
        existing.destinations = existing.destinations || [];
        existing.destinations.unshift({
          id: rec.destination_id,
          name: rec.destination_name,
          state: rec.state,
          country: "India",
          category: rec.category,
          average_budget: rec.average_budget,
          thumbnail_url: rec.thumbnail_url || "",
          mood: "Relaxing",
          budget: toMLBudget(rec.average_budget),
        });
        localStorage.setItem("travelmate_recommendations", JSON.stringify(existing));
      }
    } catch {
      // ignore
    }

    if (onSelect) {
      onSelect(rec.destination_name);
    } else {
      navigate(
        `/?destination=${encodeURIComponent(rec.destination_name)}#trip-chat-input`
      );
      setTimeout(() => {
        const el = document.getElementById("trip-chat-input");
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
          el.focus();
        }
      }, 300);
    }
  };

  if (loading) {
    return (
      <div className={`p-6 bg-card/90 backdrop-blur-md rounded-2xl border border-white/20 shadow-md ${className}`}>
        <div className="flex items-center justify-center py-6 gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground font-medium">
            Calculating personalized top recommendations...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`p-6 bg-card/90 backdrop-blur-md rounded-2xl border border-white/20 shadow-md ${className}`}>
        <div className="flex flex-col items-center py-4 gap-2 text-center">
          <AlertTriangle className="h-6 w-6 text-amber-500" />
          <p className="text-xs text-muted-foreground">{error}</p>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchRecs}
            className="flex items-center gap-1 text-xs h-7 px-3 mt-1"
          >
            <RotateCcw className="h-3 w-3" /> Retry
          </Button>
        </div>
      </div>
    );
  }

  if (recs.length === 0) return null;

  return (
    <div className={`bg-card/95 backdrop-blur-md rounded-2xl p-4 sm:p-5 shadow-xl border border-white/20 space-y-3 animate-fade-up ${className}`}>
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-coral" />
          <h3 className="text-xl font-bold tracking-tight">Popular Places</h3>
        </div>
        <span className="text-xs text-muted-foreground flex items-center gap-1">
          <TrendingUp className="h-3.5 w-3.5 text-primary" />
          Featured destinations to inspire your journey
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {recs.map((rec, idx) => {
          const rankInfo = RANK_BADGES[idx] || {
            rank: idx + 1,
            label: `#${idx + 1}`,
            color: "bg-primary text-white",
          };

          const imgSrc =
            rec.image ||
            (rec.thumbnail_url
              ? rec.thumbnail_url.startsWith("http")
                ? rec.thumbnail_url
                : `http://127.0.0.1:8000${rec.thumbnail_url}`
              : DEFAULT_IMAGE);

          const reasonText =
            rec.reason && !rec.reason.includes("%")
              ? rec.reason
              : `Explore ${rec.category || "exciting"} attractions and iconic sights in ${[rec.city, rec.state].filter(Boolean).join(", ") || "India"}`;

          return (
            <div
              key={rec.destination_id || `${rec.destination_name}-${idx}`}
              onClick={() => handleSelect(rec)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && handleSelect(rec)}
              className="group relative bg-card/70 hover:bg-card rounded-xl border border-white/10 hover:border-coral/50 overflow-hidden shadow-sm hover:shadow-md transition-all flex flex-col cursor-pointer"
            >
              {/* Image & Rank Badge */}
              <div className="relative h-36 w-full overflow-hidden bg-muted">
                <img
                  src={imgSrc}
                  alt={rec.destination_name}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = DEFAULT_IMAGE;
                  }}
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent" />

                {/* Rank Tag */}
                <span
                  className={`absolute top-2.5 left-2.5 text-[11px] font-bold px-2 py-0.5 rounded-md shadow-sm ${rankInfo.color}`}
                >
                  {rankInfo.label}
                </span>

                {/* Name on image */}
                <div className="absolute bottom-2 left-3 right-3 text-white">
                  <h4 className="font-bold text-base leading-tight drop-shadow-sm group-hover:text-coral transition-colors">
                    {rec.destination_name}
                  </h4>
                  <p className="text-[11px] text-white/80 flex items-center gap-1 mt-0.5">
                    <MapPin className="h-3 w-3 text-coral shrink-0" />
                    {[rec.city, rec.state].filter(Boolean).join(", ")}
                  </p>
                </div>
              </div>

              {/* Card Body */}
              <div className="p-3.5 flex-1 flex flex-col justify-between space-y-2.5">
                {/* Reason */}
                <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                  {reasonText}
                </p>

                {/* Meta details: Category, Cost & Duration */}
                <div className="flex items-center justify-between gap-1 text-xs pt-2 border-t border-white/10 mt-auto">
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
                    {rec.category}
                  </Badge>

                  {rec.average_budget && (
                    <span className="font-semibold text-[11px] text-foreground">
                      ₹{Math.round(rec.average_budget).toLocaleString("en-IN")}/day
                    </span>
                  )}

                  {rec.ideal_duration && (
                    <span className="text-[11px] text-muted-foreground flex items-center gap-0.5">
                      <Calendar className="h-2.5 w-2.5" />
                      {rec.ideal_duration}d
                    </span>
                  )}
                </div>

                {/* Select button */}
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full text-xs h-7 flex items-center justify-center gap-1 group-hover:bg-coral group-hover:text-white transition-colors"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSelect(rec);
                  }}
                >
                  Plan this trip <ArrowRight className="h-3 w-3" />
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default TopRecommendations;
