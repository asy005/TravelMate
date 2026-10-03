import { useState } from "react";
import { Sparkles, Filter } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const moods = ["Relaxing", "Adventure", "Romantic", "Cultural", "Nature"];
const budgets = ["Low", "Medium", "Luxury"];
const types = ["Beach", "Mountain", "City", "Forest", "Desert", "Heritage"];

export const FiltersSection = ({ onApplyFilters }: { onApplyFilters: (filters: any) => void }) => {
  const [selectedMood, setSelectedMood] = useState<string | null>(null);
  const [selectedBudget, setSelectedBudget] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<string | null>(null);

  const applyFilters = () => {
    onApplyFilters({
      mood: selectedMood,
      budget: selectedBudget,
      type: selectedType,
    });
  };

  return (
    <section className="container mx-auto px-6 py-10">
      <Card className="p-6 rounded-2xl shadow-md bg-white/60 backdrop-blur-xl border border-white/40">

        {/* HEADER */}
        <div className="flex items-center gap-3 mb-6">
          <Filter className="text-primary h-6 w-6" />
          <h2 className="text-2xl font-semibold">Find Your Perfect Destination</h2>
        </div>

        {/* FILTER BLOCKS */}
        <div className="space-y-6">

          {/* Mood */}
          <div>
            <h3 className="font-medium mb-2">Select Mood</h3>
            <div className="flex gap-3 flex-wrap">
              {moods.map((mood) => (
                <Button
                  key={mood}
                  variant={selectedMood === mood ? "default" : "outline"}
                  onClick={() => setSelectedMood(mood)}
                  className="rounded-full px-5 py-2"
                >
                  {mood}
                </Button>
              ))}
            </div>
          </div>

          {/* Budget */}
          <div>
            <h3 className="font-medium mb-2">Budget</h3>
            <div className="flex gap-3 flex-wrap">
              {budgets.map((b) => (
                <Button
                  key={b}
                  variant={selectedBudget === b ? "default" : "outline"}
                  onClick={() => setSelectedBudget(b)}
                  className="rounded-full px-5 py-2"
                >
                  {b}
                </Button>
              ))}
            </div>
          </div>

          {/* Type */}
          <div>
            <h3 className="font-medium mb-2">Destination Type</h3>
            <div className="flex gap-3 flex-wrap">
              {types.map((t) => (
                <Button
                  key={t}
                  variant={selectedType === t ? "default" : "outline"}
                  onClick={() => setSelectedType(t)}
                  className="rounded-full px-5 py-2"
                >
                  {t}
                </Button>
              ))}
            </div>
          </div>

          {/* Apply Button */}
          <div className="flex justify-center mt-6">
            <Button
              onClick={applyFilters}
              className="px-8 py-3 rounded-xl bg-primary text-white"
            >
              <Sparkles className="h-5 w-5 mr-2" /> Apply Filters
            </Button>
          </div>
        </div>
      </Card>
    </section>
  );
};
