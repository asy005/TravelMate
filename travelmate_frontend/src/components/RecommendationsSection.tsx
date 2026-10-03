import { useState, useEffect } from "react";
import { DestinationCard } from "./DestinationCard";
import { Badge } from "@/components/ui/badge";
import { Sparkles, Filter } from "lucide-react";

// -------------------------------------
// LOAD DESTINATIONS FROM LOCAL STORAGE
// -------------------------------------
const loadResults = () => {
  try {
    const saved = localStorage.getItem("travelmate_recommendations");
    if (!saved) return [];
    return JSON.parse(saved).destinations || [];
  } catch {
    return [];
  }
};

// Filter options
const moodFilters = ["All", "Relaxing", "Adventure", "Romantic"];
const budgetFilters = ["All", "Low", "Medium", "Luxury"];
const typeFilters = ["All", "Beach", "City", "Nature", "Forest", "Desert", "Heritage"];
const countryFilters = ["All", "India", "Japan", "France", "Germany", "UAE"];

export const RecommendationsSection = () => {
  const [data, setData] = useState<any[]>([]);
  const [selectedMood, setSelectedMood] = useState("All");
  const [selectedBudget, setSelectedBudget] = useState("All");
  const [selectedType, setSelectedType] = useState("All");
  const [selectedCountry, setSelectedCountry] = useState("All");

  // Load data on mount
  useEffect(() => {
    // Load initially
    setData(loadResults());
  
    // Listen for updates from HeroSection
    const handler = () => {
      setData(loadResults());
    };
  
    window.addEventListener("ai-recommendations", handler);
  
    return () => window.removeEventListener("ai-recommendations", handler);
  }, []);
  

  // Combined Filter Logic
  const filtered = data.filter((dest) => {
    const moodMatch = selectedMood === "All" || dest.mood === selectedMood;
    const budgetMatch = selectedBudget === "All" || dest.budget === selectedBudget;
    const typeMatch = selectedType === "All" || dest.type === selectedType;
    const countryMatch = selectedCountry === "All" || dest.country === selectedCountry;

    return moodMatch && budgetMatch && typeMatch && countryMatch;
  });

  const handlePlanTrip = (destination: any) => {
    console.log("Planning:", destination.name);
  };
  // Remove duplicates by destination name
  const uniqueFiltered = Array.from(
  new Map(filtered.map(dest => [dest.name, dest])).values()
  );

  return (
    <section className="py-20 bg-gradient-to-b from-background to-secondary/30">
      <div className="container mx-auto px-6">

        {/* Header */}
        <div className="text-center mb-12">
          <div className="flex items-center justify-center gap-2 mb-4">
            <Sparkles className="h-6 w-6 text-coral" />
            <h2 className="text-3xl md:text-4xl font-bold">
              Perfect Destinations for You
            </h2>
          </div>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Based on mood, budget and travel style — explore your ideal getaways
          </p>
        </div>

        {/* Filters Section */}
        <div className="space-y-6 mb-12">

          {/* Mood */}
          <div className="flex items-center gap-3 flex-wrap">
            <Filter className="h-5 w-5 text-muted-foreground" />
            <span className="font-medium text-sm">Mood:</span>
            {moodFilters.map((m) => (
              <Badge
                key={m}
                variant={selectedMood === m ? "default" : "secondary"}
                className="cursor-pointer"
                onClick={() => setSelectedMood(m)}
              >
                {m}
              </Badge>
            ))}
          </div>

          {/* Budget */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-medium text-sm">Budget:</span>
            {budgetFilters.map((b) => (
              <Badge
                key={b}
                variant={selectedBudget === b ? "default" : "secondary"}
                className="cursor-pointer"
                onClick={() => setSelectedBudget(b)}
              >
                {b}
              </Badge>
            ))}
          </div>

          {/* Destination Type */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-medium text-sm">Type:</span>
            {typeFilters.map((t) => (
              <Badge
                key={t}
                variant={selectedType === t ? "default" : "secondary"}
                className="cursor-pointer"
                onClick={() => setSelectedType(t)}
              >
                {t}
              </Badge>
            ))}
          </div>

          {/* Country */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-medium text-sm">Country:</span>
            {countryFilters.map((c) => (
              <Badge
                key={c}
                variant={selectedCountry === c ? "default" : "secondary"}
                className="cursor-pointer"
                onClick={() => setSelectedCountry(c)}
              >
                {c}
              </Badge>
            ))}
          </div>

        </div>

        {/* Destination Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {uniqueFiltered.map((destination, i) => (
          <DestinationCard
            key={i}
            destination={destination}
            onPlanTrip={handlePlanTrip}
          />
        ))}

        </div>

        {/* No Results */}
        {filtered.length === 0 && (
          <div className="text-center py-12 text-lg text-muted-foreground">
            No destinations match your filters.
          </div>
        )}
      </div>
    </section>
  );
};
