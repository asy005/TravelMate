/**
 * RecommendationsSection — Destination Explorer
 * Pulls the full 614-destination catalogue from the backend API.
 * Supports live search, category, budget, season, and state dropdown filters with pagination.
 * Filters and page changes never produce duplicate records.
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { DestinationCard } from "./DestinationCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sparkles,
  Filter,
  RotateCcw,
  Compass,
  ChevronLeft,
  ChevronRight,
  Search,
  Loader2,
  AlertTriangle,
  MapPin,
  Wallet,
  Calendar,
  X,
} from "lucide-react";
import {
  getDestinationsPage,
  getDestinationStates,
  DestinationsPage,
  resolveImageUrl,
} from "@/lib/api";

const PAGE_SIZE = 20;

const CATEGORY_FILTERS = [
  "All",
  "Beach",
  "Hill Station",
  "Heritage",
  "Urban",
  "Forest",
  "Desert",
  "Nature",
  "Adventure",
];

const BUDGET_OPTIONS = [
  { value: "All", label: "All Budgets" },
  { value: "low", label: "Budget (≤ ₹2,000)" },
  { value: "medium", label: "Mid-range (₹2,000 - ₹4,000)" },
  { value: "high", label: "Luxury (> ₹4,000)" },
];

const SEASON_OPTIONS = [
  { value: "All", label: "All Seasons" },
  { value: "winter", label: "Winter (Nov - Feb)" },
  { value: "summer", label: "Summer (Mar - Jun)" },
  { value: "monsoon", label: "Monsoon (Jul - Sep)" },
];

/**
 * Map API destination fields so DestinationCard works with both the curated
 * local shape and the live API shape.
 */
function normalizeDestination(d: any) {
  const cat = (d.category || d.type || "").toLowerCase();
  let mood = d.mood;
  if (!mood) {
    if (["beach", "nature", "forest"].includes(cat)) mood = "Relaxing";
    else if (["hill station", "adventure", "desert"].includes(cat)) mood = "Adventure";
    else if (["heritage", "urban"].includes(cat)) mood = "Romantic";
    else mood = "Relaxing";
  }

  let budget = d.budget;
  if (!budget && d.average_budget) {
    const b = Number(d.average_budget);
    if (b <= 2000) budget = "Low";
    else if (b <= 4000) budget = "Medium";
    else budget = "Luxury";
  }

  return {
    ...d,
    image: resolveImageUrl(d.image || d.thumbnail_url) || null,
    mood,
    budget,
    type: d.type || d.category,
  };
}

export const RecommendationsSection = ({ aiOutput }: { aiOutput?: string }) => {
  const navigate = useNavigate();

  // Search & filter state
  const [searchInput, setSearchInput] = useState("");
  const [committedSearch, setCommittedSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [selectedBudget, setSelectedBudget] = useState("All");
  const [selectedState, setSelectedState] = useState("All");
  const [selectedSeason, setSelectedSeason] = useState("All");

  // Dynamic states populated from the backend API
  const [availableStates, setAvailableStates] = useState<string[]>([]);
  const [loadingStates, setLoadingStates] = useState(false);

  // Pagination state
  const [page, setPage] = useState(1);

  // Data state
  const [pageData, setPageData] = useState<DestinationsPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  // Fetch available states from backend API on mount
  useEffect(() => {
    let isMounted = true;
    setLoadingStates(true);
    getDestinationStates()
      .then((states) => {
        if (isMounted && Array.isArray(states)) {
          setAvailableStates(states.filter(Boolean));
        }
      })
      .catch((err) => {
        console.warn("[RecommendationsSection] Failed to load states:", err);
      })
      .finally(() => {
        if (isMounted) setLoadingStates(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Debounced search typing
  useEffect(() => {
    const timer = setTimeout(() => {
      setCommittedSearch(searchInput.trim());
      setPage(1);
    }, 400);

    return () => clearTimeout(timer);
  }, [searchInput]);

  const fetchPage = useCallback(
    async (
      p: number,
      q: string,
      category: string,
      budget: string,
      state: string,
      season: string
    ) => {
      if (abortRef.current) abortRef.current.abort();
      abortRef.current = new AbortController();

      setLoading(true);
      setError(null);

      try {
        const data = await getDestinationsPage({
          skip: (p - 1) * PAGE_SIZE,
          limit: PAGE_SIZE,
          q: q || undefined,
          category: category !== "All" ? category : undefined,
          budget: budget !== "All" ? budget : undefined,
          state: state !== "All" ? state : undefined,
          season: season !== "All" ? season : undefined,
        });
        setPageData(data);
      } catch (err: any) {
        if (err?.name !== "AbortError") {
          setError("Could not load destinations. Please try again.");
        }
      } finally {
        setLoading(false);
      }
    },
    []
  );

  // Fetch whenever committed search, category, budget, state, season, or page changes
  useEffect(() => {
    fetchPage(page, committedSearch, selectedCategory, selectedBudget, selectedState, selectedSeason);
  }, [page, committedSearch, selectedCategory, selectedBudget, selectedState, selectedSeason, fetchPage]);

  // Re-fetch when AI recommendations event fires (to merge AI picks at top)
  useEffect(() => {
    if (aiOutput) {
      fetchPage(page, committedSearch, selectedCategory, selectedBudget, selectedState, selectedSeason);
    }
  }, [aiOutput, page, committedSearch, selectedCategory, selectedBudget, selectedState, selectedSeason, fetchPage]);

  const totalPages = pageData ? Math.ceil(pageData.total / PAGE_SIZE) : 1;
  const items = (pageData?.items || []).map(normalizeDestination);
  const totalCount = pageData?.total ?? 0;

  const handleSearchClick = () => {
    setPage(1);
    setCommittedSearch(searchInput.trim());
  };

  const handleCategoryChange = (cat: string) => {
    setSelectedCategory(cat);
    setPage(1);
  };

  const handleBudgetChange = (b: string) => {
    setSelectedBudget(b);
    setPage(1);
  };

  const handleStateChange = (st: string) => {
    setSelectedState(st);
    setPage(1);
  };

  const handleSeasonChange = (sn: string) => {
    setSelectedSeason(sn);
    setPage(1);
  };

  const handleResetFilters = () => {
    setSearchInput("");
    setCommittedSearch("");
    setSelectedCategory("All");
    setSelectedBudget("All");
    setSelectedState("All");
    setSelectedSeason("All");
    setPage(1);
  };

  const hasActiveFilters =
    committedSearch !== "" ||
    selectedCategory !== "All" ||
    selectedBudget !== "All" ||
    selectedState !== "All" ||
    selectedSeason !== "All";

  const handlePlanTrip = (destination: any) => {
    const destName = destination?.name || "";
    navigate(`/?destination=${encodeURIComponent(destName)}#trip-chat-input`);
    const inputEl = document.getElementById("trip-chat-input");
    if (inputEl) {
      inputEl.scrollIntoView({ behavior: "smooth", block: "center" });
      inputEl.focus();
    }
  };

  return (
    <section id="recommendations-section" className="py-20 bg-gradient-to-b from-background to-secondary/30">
      <div className="container mx-auto px-4 sm:px-6 max-w-7xl">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="flex items-center justify-center gap-2 mb-3">
            <Sparkles className="h-6 w-6 text-coral" />
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
              Explore Destinations
            </h2>
          </div>
          <p className="text-base sm:text-lg text-muted-foreground max-w-2xl mx-auto">
            Browse all {totalCount > 0 ? totalCount.toLocaleString() : "614+"} destinations across India — search by landmark or state, filter by budget, travel type, and season.
          </p>
        </div>

        {/* Filter / Search Card */}
        <div className="bg-card rounded-2xl border border-border/60 shadow-sm p-5 sm:p-6 mb-10 space-y-5">
          <div className="flex items-center justify-between flex-wrap gap-2 border-b border-border/50 pb-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Filter className="h-4 w-4 text-primary" />
              <span>Search &amp; Filter</span>
              {!loading && pageData && (
                <Badge variant="secondary" className="text-xs font-normal ml-2">
                  {totalCount.toLocaleString()} destinations found
                </Badge>
              )}
            </div>

            {hasActiveFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleResetFilters}
                className="text-xs h-7 px-2 text-muted-foreground hover:text-foreground flex items-center gap-1"
              >
                <RotateCcw className="h-3 w-3" /> Clear all filters
              </Button>
            )}
          </div>

          {/* Search bar & Dropdowns row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-3">
            {/* Search Input */}
            <div className="lg:col-span-5 flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search destinations by name, city, or state..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSearchClick()}
                  className="pl-9 pr-8 h-10 text-xs sm:text-sm"
                />
                {searchInput && (
                  <button
                    type="button"
                    onClick={() => {
                      setSearchInput("");
                      setCommittedSearch("");
                    }}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    title="Clear search"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
              <Button size="sm" onClick={handleSearchClick} className="shrink-0 h-10 px-4 text-xs font-medium">
                Search
              </Button>
            </div>

            {/* State Selector */}
            <div className="lg:col-span-3">
              <Select value={selectedState} onValueChange={handleStateChange}>
                <SelectTrigger className="h-10 text-xs w-full">
                  <div className="flex items-center gap-1.5 truncate">
                    <MapPin className="h-3.5 w-3.5 text-coral shrink-0" />
                    <SelectValue placeholder="All States" />
                  </div>
                </SelectTrigger>
                <SelectContent className="max-h-64">
                  <SelectItem value="All" className="text-xs font-medium">
                    All States {availableStates.length > 0 ? `(${availableStates.length})` : ""}
                  </SelectItem>
                  {availableStates.map((st) => (
                    <SelectItem key={st} value={st} className="text-xs">
                      {st}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Budget Selector */}
            <div className="lg:col-span-2">
              <Select value={selectedBudget} onValueChange={handleBudgetChange}>
                <SelectTrigger className="h-10 text-xs w-full">
                  <div className="flex items-center gap-1.5 truncate">
                    <Wallet className="h-3.5 w-3.5 text-primary shrink-0" />
                    <SelectValue placeholder="All Budgets" />
                  </div>
                </SelectTrigger>
                <SelectContent>
                  {BUDGET_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value} className="text-xs">
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Season Selector */}
            <div className="lg:col-span-2">
              <Select value={selectedSeason} onValueChange={handleSeasonChange}>
                <SelectTrigger className="h-10 text-xs w-full">
                  <div className="flex items-center gap-1.5 truncate">
                    <Calendar className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                    <SelectValue placeholder="All Seasons" />
                  </div>
                </SelectTrigger>
                <SelectContent>
                  {SEASON_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value} className="text-xs">
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Category Filter Badges */}
          <div className="flex items-center gap-2 flex-wrap pt-1">
            <span className="text-xs font-medium text-muted-foreground w-14 shrink-0">Category:</span>
            <div className="flex items-center gap-1.5 flex-wrap">
              {CATEGORY_FILTERS.map((cat) => {
                const active = selectedCategory === cat;
                return (
                  <Badge
                    key={cat}
                    variant={active ? "default" : "outline"}
                    className={`cursor-pointer transition-colors text-xs py-1 px-3 ${
                      active
                        ? "bg-primary text-primary-foreground font-medium shadow-sm"
                        : "hover:bg-muted text-muted-foreground"
                    }`}
                    onClick={() => handleCategoryChange(cat)}
                  >
                    {cat}
                  </Badge>
                );
              })}
            </div>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Searching destinations...</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
            <AlertTriangle className="h-8 w-8 text-amber-500" />
            <p className="text-sm text-destructive">{error}</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                fetchPage(page, committedSearch, selectedCategory, selectedBudget, selectedState, selectedSeason)
              }
              className="flex items-center gap-1 text-xs"
            >
              <RotateCcw className="h-3.5 w-3.5" /> Retry
            </Button>
          </div>
        ) : items.length === 0 ? (
          <div className="bg-card rounded-2xl border border-dashed border-border p-12 text-center max-w-lg mx-auto space-y-4">
            <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mx-auto text-muted-foreground">
              <Compass className="h-6 w-6" />
            </div>
            <div>
              <h3 className="font-semibold text-lg text-foreground mb-1">
                No destinations found
              </h3>
              <p className="text-sm text-muted-foreground">
                {hasActiveFilters
                  ? "No places matched your search query or selected filters. Try broadening your criteria."
                  : "The destination catalogue is currently empty."}
              </p>
            </div>
            {hasActiveFilters && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleResetFilters}
                className="inline-flex items-center gap-1 text-xs"
              >
                <RotateCcw className="h-3.5 w-3.5" /> Clear All Filters
              </Button>
            )}
          </div>
        ) : (
          <>
            {/* Destination Cards Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {items.map((destination: any) => (
                <DestinationCard
                  key={destination.id}
                  destination={destination}
                  onPlanTrip={handlePlanTrip}
                />
              ))}
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-3 mt-10">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1 || loading}
                  className="flex items-center gap-1 text-xs"
                >
                  <ChevronLeft className="h-4 w-4" /> Previous
                </Button>
                <span className="text-xs sm:text-sm text-muted-foreground font-medium px-2">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages || loading}
                  className="flex items-center gap-1 text-xs"
                >
                  Next <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
};
