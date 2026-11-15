/**
 * Favorite Places Page (/favorites)
 *
 * Exclusively displays destinations marked as favorites by the user.
 * Seamlessly synchronizes with backend database (/favorites) when authenticated,
 * and maintains resilient local storage persistence for guest or offline sessions.
 */
import { useContext, useEffect, useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { AuthContext } from "@/hooks/AuthContext";
import { Navigation } from "@/components/Navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import {
  Heart,
  MapPin,
  Trash2,
  Compass,
  ArrowRight,
  Search,
  Cloud,
  HardDrive,
  Calendar,
  Sparkles,
  DollarSign,
  Star,
  Info,
} from "lucide-react";
import {
  getFavorites,
  removeFavorite,
  resolveImageUrl,
} from "@/lib/api";

interface FavoritePlace {
  destination_name: string;
  destination_payload: any;
  saved_at?: string;
}

const FAVORITES_KEY = "travelmate_favorites";
const DEFAULT_IMAGE =
  "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&q=80&w=800";

function loadFavoriteLocations(): FavoritePlace[] {
  try {
    return JSON.parse(localStorage.getItem(FAVORITES_KEY) || "[]");
  } catch {
    return [];
  }
}

function formatDate(iso?: string) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export const Favorites = () => {
  const { token } = useContext(AuthContext);
  const navigate = useNavigate();

  const [places, setPlaces] = useState<FavoritePlace[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("All");

  const reloadFavorites = useCallback(() => {
    setPlaces(loadFavoriteLocations());
  }, []);

  useEffect(() => {
    reloadFavorites();
    setLoading(false);

    if (token) {
      getFavorites()
        .then((data: any[]) => {
          if (!Array.isArray(data) || data.length === 0) return;
          const current = loadFavoriteLocations();
          const currentNames = new Set(
            current.map((f) => (f.destination_name || "").toLowerCase())
          );
          let changed = false;

          for (const item of data) {
            const name = item.name || item.destination_name || "";
            if (name && !currentNames.has(name.toLowerCase())) {
              current.push({
                destination_name: name,
                destination_payload: item,
                saved_at: item.saved_at || new Date().toISOString(),
              });
              changed = true;
            }
          }

          if (changed) {
            localStorage.setItem(FAVORITES_KEY, JSON.stringify(current));
            setPlaces([...current]);
          }
        })
        .catch(() => {
          // Fall back gracefully to local records
        });
    }

    const handler = () => reloadFavorites();
    window.addEventListener("travelmate_favorites_changed", handler);
    return () => window.removeEventListener("travelmate_favorites_changed", handler);
  }, [token, reloadFavorites]);

  const removeFavoritePlace = (name: string) => {
    const updated = places.filter(
      (p) => (p.destination_name || "").toLowerCase() !== name.toLowerCase()
    );
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(updated));
    setPlaces(updated);

    // Notify DestinationCard instances to update their heart icon
    window.dispatchEvent(new CustomEvent("travelmate_favorites_changed"));

    if (token) {
      const payload = places.find(
        (p) => (p.destination_name || "").toLowerCase() === name.toLowerCase()
      );
      const destId = payload?.destination_payload?.id;
      if (destId) {
        removeFavorite(destId).catch(() => {
          // Local removal already succeeded
        });
      }
    }
  };

  // Distinct categories for quick filter pills
  const categories = useMemo(() => {
    const set = new Set<string>();
    places.forEach((p) => {
      const cat =
        p.destination_payload?.category ||
        p.destination_payload?.type ||
        "General";
      if (cat) set.add(cat);
    });
    return ["All", ...Array.from(set)];
  }, [places]);

  // Filtered places based on search query and category
  const filteredPlaces = useMemo(() => {
    return places.filter((p) => {
      const dest = p.destination_payload || {};
      const name = (p.destination_name || dest.name || "").toLowerCase();
      const state = (dest.state || dest.region || "").toLowerCase();
      const country = (dest.country || "India").toLowerCase();
      const cat = (dest.category || dest.type || "").toLowerCase();
      const q = searchQuery.trim().toLowerCase();

      const matchesSearch =
        !q ||
        name.includes(q) ||
        state.includes(q) ||
        country.includes(q) ||
        cat.includes(q);

      const matchesCategory =
        selectedCategory === "All" ||
        (dest.category || dest.type || "General").toLowerCase() ===
          selectedCategory.toLowerCase();

      return matchesSearch && matchesCategory;
    });
  }, [places, searchQuery, selectedCategory]);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navigation />

      <main className="flex-1 container mx-auto px-4 sm:px-6 max-w-7xl pt-28 pb-20 space-y-8 animate-fade-up">
        {/* ── Page Header ── */}
        <div className="bg-card rounded-3xl p-6 sm:p-8 border border-border/60 shadow-sm relative overflow-hidden">
          <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="flex items-start gap-4">
              <div className="h-14 w-14 rounded-2xl bg-coral/10 text-coral flex items-center justify-center shrink-0 shadow-inner">
                <Heart className="h-7 w-7 fill-coral text-coral" aria-hidden="true" />
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center gap-3 flex-wrap">
                  <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground">
                    Favorite Destinations
                  </h1>
                  <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-semibold">
                    {places.length} {places.length === 1 ? "Place" : "Places"}
                  </Badge>
                  {token ? (
                    <Badge
                      variant="outline"
                      className="text-xs px-2.5 py-0.5 border-emerald-500/40 text-emerald-600 dark:text-emerald-400 bg-emerald-500/5 flex items-center gap-1"
                    >
                      <Cloud className="h-3 w-3" /> Account Synced
                    </Badge>
                  ) : (
                    <Badge
                      variant="outline"
                      className="text-xs px-2.5 py-0.5 border-amber-500/40 text-amber-600 dark:text-amber-400 bg-amber-500/5 flex items-center gap-1"
                    >
                      <HardDrive className="h-3 w-3" /> Saved on Device
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
                  Your curated wishlist of dream destinations across India. Review highlights, customize itineraries, or plan your next journey anytime.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 self-start md:self-auto">
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate("/saved-trips")}
                className="text-xs font-medium h-9 px-3 gap-1.5 border-border hover:bg-muted"
              >
                <Compass className="h-4 w-4 text-primary" />
                View Saved Trips
              </Button>
            </div>
          </div>

          {!token && places.length > 0 && (
            <div className="mt-6 pt-4 border-t border-border/50 flex items-center gap-2 text-xs text-muted-foreground">
              <Info className="h-4 w-4 text-amber-500 shrink-0" />
              <span>
                You are browsing offline/device favorites.{" "}
                <button
                  onClick={() => navigate("/login")}
                  className="font-semibold text-primary underline hover:text-primary/80"
                >
                  Sign in
                </button>{" "}
                to securely back up your saved destinations across all devices.
              </span>
            </div>
          )}
        </div>

        {/* ── Search & Filter Bar (Shown when favorites exist) ── */}
        {places.length > 0 && (
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search favorite destinations, states, or styles..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 h-10 text-xs rounded-xl bg-card border-border/60"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground hover:text-foreground"
                >
                  Clear
                </button>
              )}
            </div>

            {categories.length > 2 && (
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
                {categories.map((cat) => (
                  <Button
                    key={cat}
                    variant={selectedCategory === cat ? "default" : "outline"}
                    size="sm"
                    onClick={() => setSelectedCategory(cat)}
                    className="text-xs h-8 px-3 rounded-full shrink-0"
                  >
                    {cat}
                  </Button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Content Grid or Empty States ── */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6" aria-busy="true">
            {[...Array(6)].map((_, i) => (
              <Card key={i} className="overflow-hidden rounded-2xl border border-border/60 p-0">
                <Skeleton className="h-48 w-full" />
                <div className="p-5 space-y-3">
                  <Skeleton className="h-5 w-2/3" />
                  <Skeleton className="h-4 w-1/2" />
                  <div className="pt-2 flex justify-between gap-2">
                    <Skeleton className="h-8 w-1/2 rounded-xl" />
                    <Skeleton className="h-8 w-1/2 rounded-xl" />
                  </div>
                </div>
              </Card>
            ))}
          </div>
        ) : places.length === 0 ? (
          <div className="bg-card rounded-3xl p-8 sm:p-12 border border-border/60 text-center shadow-sm">
            <EmptyState
              icon={Heart}
              title="Your travel wishlist is empty"
              description="Explore handpicked destinations, discover historic heritage sites, tropical atolls, and serene hill stations, then tap the heart icon to save your favorites here."
              actionLabel="Discover Destinations"
              onAction={() => navigate("/#recommendations-section")}
            />
          </div>
        ) : filteredPlaces.length === 0 ? (
          <div className="bg-card rounded-3xl p-8 border border-border/60 text-center space-y-3">
            <p className="text-sm font-semibold text-foreground">
              No favorites match "{searchQuery}"
            </p>
            <p className="text-xs text-muted-foreground">
              Try adjusting your search terms or clearing active filters.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSearchQuery("");
                setSelectedCategory("All");
              }}
              className="text-xs"
            >
              Reset Filters
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredPlaces.map((place) => {
              const dest = place.destination_payload || {};
              const name = place.destination_name || dest.name || "Unknown Destination";
              const country = dest.country || "India";
              const state = dest.state || dest.region || "";
              const resolvedHero =
                resolveImageUrl(dest.image || dest.thumbnail_url) || DEFAULT_IMAGE;
              const category = dest.category || dest.type || "Attraction";
              const budget = dest.budget || dest.average_budget;
              const duration = dest.ideal_duration || dest.duration;
              const rating = dest.rating;
              const destTarget = dest.id || encodeURIComponent(name);

              return (
                <Card
                  key={name}
                  className="group overflow-hidden rounded-2xl bg-card border border-border/60 hover:border-primary/40 shadow-sm hover:shadow-md transition-all duration-300 flex flex-col h-full"
                >
                  {/* Destination Cover Image */}
                  <div className="relative aspect-[16/10] w-full overflow-hidden bg-muted">
                    <img
                      src={resolvedHero}
                      alt={name}
                      loading="lazy"
                      onError={(e) => {
                        (e.target as HTMLImageElement).src = DEFAULT_IMAGE;
                      }}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/20 to-transparent" />

                    {/* Top Pill Badges */}
                    <div className="absolute top-3 left-3 flex items-center gap-1.5 flex-wrap max-w-[70%]">
                      <Badge className="bg-black/60 backdrop-blur-md text-white border-white/20 text-[11px] font-medium shadow-sm">
                        {category}
                      </Badge>
                      {rating && (
                        <Badge className="bg-amber-500/90 text-white border-0 text-[11px] font-semibold flex items-center gap-1 shadow-sm">
                          <Star className="h-3 w-3 fill-white" />
                          {Number(rating).toFixed(1)}
                        </Badge>
                      )}
                    </div>

                    {/* Remove Favorite Button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFavoritePlace(name);
                      }}
                      className="absolute top-3 right-3 h-8 w-8 rounded-full bg-background/85 backdrop-blur-md flex items-center justify-center text-red-500 hover:bg-background transition-colors shadow-sm"
                      title="Remove from favorites"
                      aria-label={`Remove ${name} from favorites`}
                    >
                      <Heart className="h-4 w-4 fill-red-500 text-red-500" />
                    </button>

                    {/* Destination Title on Image */}
                    <div className="absolute bottom-3 left-3 right-3">
                      <h3 className="text-lg font-bold text-white drop-shadow-sm truncate">
                        {name}
                      </h3>
                      <p className="text-xs text-white/85 flex items-center gap-1 drop-shadow-sm truncate">
                        <MapPin className="h-3 w-3 text-coral shrink-0" />
                        {[state, country].filter(Boolean).join(", ")}
                      </p>
                    </div>
                  </div>

                  {/* Card Content & Metadata */}
                  <div className="p-4 sm:p-5 flex-1 flex flex-col justify-between gap-4">
                    <div className="space-y-2.5">
                      {/* Meta Tags Row */}
                      <div className="flex items-center gap-2 flex-wrap">
                        {budget && (
                          <Badge variant="outline" className="text-[11px] px-2 py-0.5 h-5 font-medium border-border/80">
                            <DollarSign className="h-3 w-3 text-emerald-600 mr-0.5" />
                            {typeof budget === "number"
                              ? `₹${budget.toLocaleString("en-IN")}`
                              : budget}
                          </Badge>
                        )}

                        {duration && (
                          <Badge variant="outline" className="text-[11px] px-2 py-0.5 h-5 font-medium border-border/80">
                            <Calendar className="h-3 w-3 text-primary mr-1" />
                            {duration} Days
                          </Badge>
                        )}

                        {place.saved_at && (
                          <span className="text-[10px] text-muted-foreground ml-auto">
                            Added {formatDate(place.saved_at)}
                          </span>
                        )}
                      </div>

                      {dest.description && (
                        <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                          {dest.description}
                        </p>
                      )}
                    </div>

                    {/* Uniform Footer Actions */}
                    <div className="pt-3 border-t border-border/50 grid grid-cols-2 gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(`/destination/${destTarget}`)}
                        className="text-xs font-semibold h-8 rounded-xl border-border/80 hover:bg-muted gap-1"
                      >
                        View Details
                      </Button>

                      <Button
                        size="sm"
                        onClick={() =>
                          navigate(
                            dest.id
                              ? `/destination/${dest.id}#itinerary-builder`
                              : `/?destination=${encodeURIComponent(name)}#trip-chat-input`
                          )
                        }
                        className="text-xs font-semibold h-8 rounded-xl gap-1 shadow-sm"
                      >
                        <Compass className="h-3.5 w-3.5" />
                        Plan Trip
                      </Button>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
};

export default Favorites;
