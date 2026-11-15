import { useState, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Loader2,
  Backpack,
  RefreshCcw,
  AlertCircle,
  CheckCircle2,
  Circle,
  CloudRain,
  Sun,
  Snowflake,
  Thermometer,
  Cloud,
  Plus,
  Trash2,
  Edit2,
  Check,
  X,
} from "lucide-react";
import { generatePackingList } from "@/lib/api";

interface PackingListBoxProps {
  destination?: any;
  weather?: any;
  selectedActivities?: any[];
  initialPackingList?: string[];
  initialPackedItems?: Record<string, boolean>;
  initialCustomItems?: string[];
  onStateChange?: (state: {
    packingList: string[];
    packedItems: Record<string, boolean>;
    customItems: string[];
  }) => void;
}

export const PackingListBox = ({
  destination,
  weather,
  selectedActivities,
  initialPackingList,
  initialPackedItems,
  initialCustomItems,
  onStateChange,
}: PackingListBoxProps) => {
  const destName =
    typeof destination === "string" ? destination : destination?.name || "";
  const destId =
    typeof destination === "object" ? destination?.id || destName : destName;

  const [days, setDays] = useState(3);
  const [activities, setActivities] = useState("Sightseeing, Dining");
  const [packingList, setPackingList] = useState<string[]>(initialPackingList || []);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Custom user items state
  const customItemsStorageKey = `travelmate_packing_custom_${destId}`;
  const [customItems, setCustomItems] = useState<string[]>(() => {
    if (initialCustomItems && initialCustomItems.length > 0) return initialCustomItems;
    try {
      const saved = localStorage.getItem(customItemsStorageKey);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Persistent checklist state keyed by destination ID
  const storageKey = `travelmate_packing_checklist_${destId}`;
  const [packedItems, setPackedItems] = useState<Record<string, boolean>>(() => {
    if (initialPackedItems && Object.keys(initialPackedItems).length > 0)
      return initialPackedItems;
    try {
      const saved = localStorage.getItem(storageKey);
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  // New custom item input & edit state
  const [newCustomItemText, setNewCustomItemText] = useState("");
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingText, setEditingText] = useState("");

  // Update activities when selectedActivities change
  useEffect(() => {
    if (selectedActivities && selectedActivities.length > 0) {
      const names = selectedActivities.map((a: any) =>
        typeof a === "string" ? a : a.name
      );
      setActivities((prev) => {
        const existing = prev.split(",").map((x) => x.trim()).filter(Boolean);
        const merged = Array.from(new Set([...existing, ...names]));
        return merged.join(", ");
      });
    }
  }, [selectedActivities]);

  // Keep localStorage updated when packedItems changes
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(packedItems));
    } catch {}
  }, [packedItems, storageKey]);

  // Keep custom items stored in localStorage
  useEffect(() => {
    try {
      localStorage.setItem(customItemsStorageKey, JSON.stringify(customItems));
    } catch {}
  }, [customItems, customItemsStorageKey]);

  // Notify parent component of packing state change
  useEffect(() => {
    if (onStateChange) {
      onStateChange({
        packingList,
        packedItems,
        customItems,
      });
    }
  }, [packingList, packedItems, customItems, onStateChange]);

  // If initial values are updated from a saved trip restore
  useEffect(() => {
    if (initialPackingList && initialPackingList.length > 0) {
      setPackingList(initialPackingList);
    }
    if (initialCustomItems && initialCustomItems.length > 0) {
      setCustomItems(initialCustomItems);
    }
    if (initialPackedItems && Object.keys(initialPackedItems).length > 0) {
      setPackedItems(initialPackedItems);
    }
  }, [initialPackingList, initialCustomItems, initialPackedItems]);

  // Derive weather information automatically from Open-Meteo weather object
  const weatherAnalysis = useMemo(() => {
    if (!weather) {
      return {
        available: false,
        tempText: null,
        condition: null,
        climateKeyword: "moderate",
        icon: null,
        advice: "Regional seasonal packing recommendation.",
      };
    }

    const temp =
      weather.temperature !== undefined
        ? Number(weather.temperature)
        : weather.temperature_2m !== undefined
        ? Number(weather.temperature_2m)
        : null;

    if (temp === null) {
      return {
        available: false,
        tempText: null,
        condition: null,
        climateKeyword: "moderate",
        icon: null,
        advice: "Regional seasonal packing recommendation.",
      };
    }

    const code = Number(
      weather.weathercode !== undefined
        ? weather.weathercode
        : weather.weather_code !== undefined
        ? weather.weather_code
        : -1
    );

    const isRain =
      [51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99].includes(code);
    const isSnow = [71, 73, 75].includes(code);

    let climateKeyword = "moderate";
    let condition = "Pleasant / Moderate";
    let icon = <Cloud className="h-4 w-4 text-sky-500 shrink-0" />;
    let advice = "Comfortable everyday attire and light layers.";

    if (isSnow || temp < 10) {
      climateKeyword = "cold snow";
      condition = isSnow ? "Snowy & Cold" : "Cold";
      icon = <Snowflake className="h-4 w-4 text-blue-400 shrink-0" />;
      advice =
        "Freezing temperatures expected. Pack thermal layers, heavy coat, and gloves.";
    } else if (isRain) {
      climateKeyword = temp > 25 ? "rain hot" : "rain cold";
      condition = "Rain & Showers";
      icon = <CloudRain className="h-4 w-4 text-indigo-500 shrink-0" />;
      advice =
        "Precipitation forecast. Pack a compact umbrella, waterproof jacket, and dry bags.";
    } else if (temp > 28) {
      climateKeyword = "hot sun";
      condition = "Warm & Sunny";
      icon = <Sun className="h-4 w-4 text-amber-500 shrink-0" />;
      advice =
        "High daytime temperatures. Pack light breathable clothes, SPF 50 sunscreen, and sunglasses.";
    } else if (temp < 18) {
      climateKeyword = "cold";
      condition = "Cool / Chilly";
      icon = <Thermometer className="h-4 w-4 text-cyan-600 shrink-0" />;
      advice =
        "Cool breezes likely. Pack a warm fleece or jacket for mornings and evenings.";
    }

    return {
      available: true,
      tempText: `${Math.round(temp)}°C`,
      condition,
      climateKeyword,
      icon,
      advice,
    };
  }, [weather]);

  const generateList = async () => {
    if (!destName) return;
    setLoading(true);
    setError(null);

    try {
      const data = await generatePackingList({
        destination: destName,
        days: Math.max(1, Math.min(30, Number(days) || 3)),
        weather: weatherAnalysis.available
          ? weatherAnalysis.climateKeyword
          : undefined,
        activities: activities
          ? activities.split(",").map((x) => x.trim()).filter(Boolean)
          : [],
      });
      setPackingList(data.packing_list || []);
    } catch (err: any) {
      console.error("Packing error:", err);
      setError("Unable to generate packing list. Please retry.");
      setPackingList([]);
    } finally {
      setLoading(false);
    }
  };

  const toggleItemPacked = (item: string) => {
    setPackedItems((prev) => ({
      ...prev,
      [item]: !prev[item],
    }));
  };

  const handleAddCustomItem = () => {
    const trimmed = newCustomItemText.trim();
    if (!trimmed) return;
    if (customItems.includes(trimmed) || packingList.includes(trimmed)) {
      setNewCustomItemText("");
      return;
    }
    setCustomItems((prev) => [...prev, trimmed]);
    setNewCustomItemText("");
  };

  const handleRemoveCustomItem = (itemToRemove: string) => {
    setCustomItems((prev) => prev.filter((item) => item !== itemToRemove));
    setPackedItems((prev) => {
      const copy = { ...prev };
      delete copy[itemToRemove];
      return copy;
    });
  };

  const handleStartEdit = (index: number, currentText: string) => {
    setEditingIndex(index);
    setEditingText(currentText);
  };

  const handleSaveEdit = (oldItem: string) => {
    const trimmed = editingText.trim();
    if (!trimmed || trimmed === oldItem) {
      setEditingIndex(null);
      return;
    }
    setCustomItems((prev) =>
      prev.map((item) => (item === oldItem ? trimmed : item))
    );
    setPackedItems((prev) => {
      const copy = { ...prev };
      if (copy[oldItem] !== undefined) {
        copy[trimmed] = copy[oldItem];
        delete copy[oldItem];
      }
      return copy;
    });
    setEditingIndex(null);
  };

  // Combine items for counts
  const allItems = useMemo(
    () => [...packingList, ...customItems],
    [packingList, customItems]
  );
  const totalCount = allItems.length;
  const packedCount = allItems.filter((item) => packedItems[item]).length;
  const progressPercent =
    totalCount > 0 ? Math.round((packedCount / totalCount) * 100) : 0;

  return (
    <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
            <Backpack className="h-5 w-5 text-coral" />
            <span>Smart Packing List</span>
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Weather-aware wardrobe and essential gear tailored to your duration, climate, and activities.
          </p>
        </div>

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

      {/* Automatic Weather Status Banner */}
      {weatherAnalysis.available ? (
        <div className="p-3 bg-muted/40 rounded-xl border border-border/50 flex flex-wrap items-center justify-between gap-2.5 text-xs">
          <div className="flex items-center gap-2">
            {weatherAnalysis.icon}
            <span className="font-semibold text-foreground">
              Live Forecast: {weatherAnalysis.tempText} • {weatherAnalysis.condition}
            </span>
          </div>
          <span className="text-muted-foreground italic text-[11px]">
            {weatherAnalysis.advice}
          </span>
        </div>
      ) : (
        <div className="p-3 bg-amber-500/10 border border-amber-500/20 text-amber-800 dark:text-amber-300 rounded-xl text-xs flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-amber-600" />
          <span>
            Forecast currently unavailable for this destination. Recommendations will be tailored using regional climate, trip duration, and planned activities.
          </span>
        </div>
      )}

      {/* Duration and Activities inputs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-muted-foreground block mb-1 font-medium">
            Trip Duration (days)
          </label>
          <Input
            type="number"
            min={1}
            max={30}
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="text-xs h-9"
            placeholder="Duration in days"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground block mb-1 font-medium">
            Planned Activities
          </label>
          <Input
            placeholder="e.g. hiking, beach, temple, formal dining..."
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
          <span>Crafting smart travel checklist for {destName}...</span>
        </div>
      )}

      {/* Custom Item Addition Bar */}
      <div className="flex items-center gap-2 pt-1">
        <Input
          type="text"
          value={newCustomItemText}
          onChange={(e) => setNewCustomItemText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              handleAddCustomItem();
            }
          }}
          placeholder="Add your own custom packing item (e.g. Passport, Camera, Medicine)..."
          className="text-xs h-8 flex-1"
        />
        <Button
          type="button"
          onClick={handleAddCustomItem}
          disabled={!newCustomItemText.trim()}
          size="sm"
          variant="outline"
          className="text-xs h-8 px-3 shrink-0 flex items-center gap-1"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>Add Item</span>
        </Button>
      </div>

      {/* Interactive Packing Checklist */}
      {!loading && (packingList.length > 0 || customItems.length > 0) && (
        <div className="space-y-3 pt-2">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-foreground">
                Checklist Items
              </span>
              <Badge
                variant={packedCount === totalCount ? "default" : "secondary"}
                className="text-[11px] font-medium"
              >
                {packedCount} / {totalCount} packed ({progressPercent}%)
              </Badge>
            </div>
            {packedCount > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setPackedItems({})}
                className="text-[11px] h-6 px-2 text-muted-foreground hover:text-foreground"
              >
                Reset checks
              </Button>
            )}
          </div>

          {/* Progress Bar */}
          <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-primary h-full transition-all duration-300 rounded-full"
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          {/* Clickable Items Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5 pt-1">
            {/* Standard Generated Items */}
            {packingList.map((item, i) => {
              const isPacked = !!packedItems[item];
              return (
                <button
                  key={`std-${i}`}
                  type="button"
                  onClick={() => toggleItemPacked(item)}
                  className={`p-2.5 rounded-xl border text-xs flex items-center gap-2.5 text-left transition-all ${
                    isPacked
                      ? "bg-primary/10 border-primary/30 text-muted-foreground line-through opacity-80"
                      : "bg-muted/40 hover:bg-muted/70 border-border/50 text-foreground hover:border-primary/40 shadow-xs"
                  }`}
                  aria-pressed={isPacked}
                >
                  {isPacked ? (
                    <CheckCircle2 className="h-4 w-4 text-primary shrink-0 transition-transform scale-110" />
                  ) : (
                    <Circle className="h-4 w-4 text-muted-foreground shrink-0" />
                  )}
                  <span className="truncate flex-1">{item}</span>
                </button>
              );
            })}

            {/* Custom User-Added Items */}
            {customItems.map((item, i) => {
              const isPacked = !!packedItems[item];
              const isEditing = editingIndex === i;

              if (isEditing) {
                return (
                  <div
                    key={`custom-${i}`}
                    className="p-1.5 rounded-xl border border-primary/50 bg-background flex items-center gap-1.5 shadow-xs"
                  >
                    <Input
                      type="text"
                      value={editingText}
                      onChange={(e) => setEditingText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleSaveEdit(item);
                        if (e.key === "Escape") setEditingIndex(null);
                      }}
                      className="text-xs h-7 px-2 flex-1"
                      autoFocus
                    />
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleSaveEdit(item)}
                      className="h-6 w-6 p-0 text-emerald-600"
                      title="Save"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setEditingIndex(null)}
                      className="h-6 w-6 p-0 text-muted-foreground"
                      title="Cancel"
                    >
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                );
              }

              return (
                <div
                  key={`custom-${i}`}
                  className={`group p-2.5 rounded-xl border text-xs flex items-center gap-2 transition-all ${
                    isPacked
                      ? "bg-primary/10 border-primary/30 text-muted-foreground opacity-80"
                      : "bg-primary/5 hover:bg-primary/10 border-primary/20 text-foreground"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => toggleItemPacked(item)}
                    className="flex items-center gap-2 flex-1 min-w-0 text-left"
                    aria-pressed={isPacked}
                  >
                    {isPacked ? (
                      <CheckCircle2 className="h-4 w-4 text-primary shrink-0 transition-transform scale-110" />
                    ) : (
                      <Circle className="h-4 w-4 text-primary shrink-0" />
                    )}
                    <span
                      className={`truncate flex-1 ${
                        isPacked ? "line-through text-muted-foreground" : "font-medium"
                      }`}
                    >
                      {item}
                    </span>
                    <Badge
                      variant="outline"
                      className="text-[9px] py-0 px-1 h-3.5 text-primary border-primary/40 shrink-0"
                    >
                      Custom
                    </Badge>
                  </button>

                  <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      type="button"
                      onClick={() => handleStartEdit(i, item)}
                      className="p-1 hover:text-primary text-muted-foreground rounded"
                      title="Edit item"
                    >
                      <Edit2 className="h-3 w-3" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleRemoveCustomItem(item)}
                      className="p-1 hover:text-destructive text-muted-foreground rounded"
                      title="Remove item"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {!loading && !error && packingList.length === 0 && customItems.length === 0 && (
        <p className="text-xs text-muted-foreground italic py-1">
          Click "Generate Packing List" or add your own custom items above to build an interactive, weather-optimized checklist for {destName || "your trip"}.
        </p>
      )}
    </div>
  );
};
