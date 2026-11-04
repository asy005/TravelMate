/**
 * Favorites page — two distinct sections:
 *   1. Favorite Places — destinations saved locally (localStorage) and optionally
 *      synced to the backend when the user is logged in.
 *   2. Saved Trips — trip plans saved from the AI chat (localStorage, device-local).
 *
 * Removal is reflected immediately in both this page and the DestinationCard heart
 * icon via a shared `travelmate_favorites` localStorage key and a custom event.
 */
import { useContext, useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { AuthContext } from "@/hooks/AuthContext";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import {
  Heart,
  MapPin,
  Trash2,
  Compass,
  Calendar,
  DollarSign,
  ArrowRight,
  Info,
} from "lucide-react";
import { getFavorites, removeFavorite, resolveImageUrl } from "@/lib/api";

// ─── Types ───────────────────────────────────────────────────────────────────

interface FavoritePlace {
  destination_name: string;
  destination_payload: any;
  saved_at?: string;
}

interface SavedTrip {
  session_id: string;
  plan: any;
  saved_at: string;
  destination?: string;
}

// ─── Storage Keys ─────────────────────────────────────────────────────────────

const FAVORITES_KEY = "travelmate_favorites";
const SAVED_TRIPS_KEY = "travelmate_saved_trips";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function loadFavoriteLocations(): FavoritePlace[] {
  try {
    return JSON.parse(localStorage.getItem(FAVORITES_KEY) || "[]");
  } catch {
    return [];
  }
}

function loadSavedTrips(): SavedTrip[] {
  try {
    return JSON.parse(localStorage.getItem(SAVED_TRIPS_KEY) || "[]");
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

// ─── Component ────────────────────────────────────────────────────────────────

const Favorites = () => {
  const { token } = useContext(AuthContext);
  const navigate = useNavigate();

  // Favorite Places state
  const [places, setPlaces] = useState<FavoritePlace[]>([]);
  const [placesLoading, setPlacesLoading] = useState(true);

  // Saved Trips state
  const [trips, setTrips] = useState<SavedTrip[]>([]);

  // ── Load on mount ────────────────────────────────────────────────────────────

  const reloadFavorites = useCallback(() => {
    setPlaces(loadFavoriteLocations());
    setTrips(loadSavedTrips());
  }, []);

  useEffect(() => {
    reloadFavorites();
    setPlacesLoading(false);

    // Also sync with backend favorites if logged in
    if (token) {
      getFavorites()
        .then((data: any[]) => {
          if (!Array.isArray(data) || data.length === 0) return;
          // Merge backend favorites into localStorage (add any missing ones)
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
          // Backend not reachable — local data is shown
        });
    }

    // Listen for changes made by DestinationCard in another component
    const handler = () => reloadFavorites();
    window.addEventListener("travelmate_favorites_changed", handler);
    return () => window.removeEventListener("travelmate_favorites_changed", handler);
  }, [token, reloadFavorites]);

  // ── Remove favorite place ─────────────────────────────────────────────────────

  const removeFavoritePlace = (name: string) => {
    const updated = places.filter(
      (p) => (p.destination_name || "").toLowerCase() !== name.toLowerCase()
    );
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(updated));
    setPlaces(updated);
    // Notify DestinationCard instances about the change so their heart icon updates
    window.dispatchEvent(new CustomEvent("travelmate_favorites_changed"));

    // Best-effort backend removal if logged in
    if (token) {
      const payload = places.find(
        (p) => (p.destination_name || "").toLowerCase() === name.toLowerCase()
      );
      const destId = payload?.destination_payload?.id;
      if (destId) {
        removeFavorite(destId).catch(() => {
          // ignore — local removal already done
        });
      }
    }
  };

  // ── Remove saved trip ─────────────────────────────────────────────────────────

  const removeSavedTrip = (sessionId: string) => {
    const updated = trips.filter((t) => t.session_id !== sessionId);
    localStorage.setItem(SAVED_TRIPS_KEY, JSON.stringify(updated));
    setTrips(updated);
  };

  // ── Resume trip ───────────────────────────────────────────────────────────────

  const resumeTrip = (trip: SavedTrip) => {
    // Store session id so HeroSection picks it up on next load
    localStorage.setItem("travelmate_assistant_session", trip.session_id);
    navigate("/");
    setTimeout(() => {
      document.getElementById("trip-chat-input")?.focus();
    }, 500);
  };

  // ─── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="container mx-auto px-6 max-w-4xl pt-28 pb-16 space-y-12">
      {/* ───── Favorite Places ───── */}
      <section aria-labelledby="fav-places-heading">
        <div className="flex items-center gap-2 mb-6">
          <Heart className="h-6 w-6 text-coral" aria-hidden="true" />
          <h1 id="fav-places-heading" className="text-3xl font-bold">
            Favorite Places
          </h1>
        </div>

        {placesLoading ? (
          <div
            className="grid sm:grid-cols-2 gap-4"
            aria-busy="true"
            aria-label="Loading favourite places"
          >
            {[...Array(4)].map((_, i) => (
              <Card key={i} className="p-4 border border-white/10">
                <Skeleton className="h-5 w-2/3 mb-2" />
                <Skeleton className="h-4 w-1/3" />
              </Card>
            ))}
          </div>
        ) : places.length === 0 ? (
          <EmptyState
            icon={Heart}
            title="No favourite places yet"
            description="Tap the ♥ heart on any destination card to save it here. Saved places are stored on this device and synced to your account when logged in."
            actionLabel="Browse destinations"
            onAction={() => navigate("/#recommendations-section")}
          />
        ) : (
          <div className="grid sm:grid-cols-2 gap-4">
            {places.map((place) => {
              const dest = place.destination_payload || {};
              const name = place.destination_name || dest.name || "Unknown";
              const country = dest.country || "India";
              const state = dest.state || dest.region || "";
              const image =
                dest.image ||
                (dest.thumbnail_url ? resolveImageUrl(dest.thumbnail_url) : null);
              const budget = dest.budget;
              const type = dest.type || dest.category;

              return (
                <Card
                  key={name}
                  className="overflow-hidden bg-card/95 backdrop-blur-md border border-white/20 flex flex-col animate-fade-up hover:border-primary/40 transition-all"
                >
                  {/* Image strip */}
                  {image && (
                    <div className="h-32 w-full overflow-hidden">
                      <img
                        src={image}
                        alt={name}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = "none";
                        }}
                      />
                    </div>
                  )}

                  <div className="p-4 flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      <div className="h-9 w-9 rounded-full bg-coral/15 flex items-center justify-center shrink-0 mt-0.5">
                        <MapPin className="h-4 w-4 text-coral" aria-hidden="true" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-semibold truncate">{name}</p>
                        <p className="text-xs text-muted-foreground">
                          {[state, country].filter(Boolean).join(", ")}
                        </p>
                        <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                          {type && (
                            <Badge variant="outline" className="text-[11px] px-1.5 py-0 h-5">
                              {type}
                            </Badge>
                          )}
                          {budget && (
                            <Badge variant="secondary" className="text-[11px] px-1.5 py-0 h-5">
                              {budget}
                            </Badge>
                          )}
                        </div>
                        {place.saved_at && (
                          <p className="text-[10px] text-muted-foreground mt-1">
                            Saved {formatDate(place.saved_at)}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex flex-col items-end gap-2 shrink-0">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                        title="Remove from favourites"
                        onClick={() => removeFavoritePlace(name)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-xs h-7 px-2"
                        onClick={() =>
                          navigate(
                            `/destination/${dest.id || encodeURIComponent(name)}`
                          )
                        }
                      >
                        View
                      </Button>
                      <Button
                        size="sm"
                        className="text-xs h-7 px-2 flex items-center gap-1"
                        onClick={() =>
                          navigate(
                            `/?destination=${encodeURIComponent(name)}#trip-chat-input`
                          )
                        }
                      >
                        <Compass className="h-3 w-3" /> Plan
                      </Button>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {/* ───── Saved Trips ───── */}
      <section aria-labelledby="saved-trips-heading">
        <div className="flex items-center gap-2 mb-2">
          <Calendar className="h-6 w-6 text-primary" aria-hidden="true" />
          <h2 id="saved-trips-heading" className="text-3xl font-bold">
            Saved Trips
          </h2>
        </div>

        {/* Device-local notice */}
        <div className="flex items-start gap-2 p-3 mb-5 bg-sky/10 border border-sky/30 rounded-xl text-xs text-sky-700 dark:text-sky-300">
          <Info className="h-4 w-4 shrink-0 mt-0.5" />
          <span>
            Saved trips are stored on <strong>this device only</strong>. They are not synced to
            your account. To preserve a trip, export or bookmark the page before clearing
            browser data.
          </span>
        </div>

        {trips.length === 0 ? (
          <EmptyState
            icon={Calendar}
            title="No saved trips yet"
            description="When the AI assistant generates a travel plan you like, it will appear here so you can come back and resume or revisit it."
            actionLabel="Plan a trip now"
            onAction={() => navigate("/")}
          />
        ) : (
          <div className="grid sm:grid-cols-2 gap-4">
            {trips.map((trip) => {
              const dest =
                trip.destination || trip.plan?.destination || trip.plan?.trip?.destination || "";
              const budget = trip.plan?.budget || trip.plan?.trip?.budget || "";
              const days =
                trip.plan?.duration_days ||
                trip.plan?.trip?.duration_days ||
                trip.plan?.duration ||
                "";

              return (
                <Card
                  key={trip.session_id}
                  className="p-4 bg-card/95 backdrop-blur-md border border-white/20 flex flex-col gap-3 animate-fade-up hover:border-primary/40 transition-all"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <div className="h-9 w-9 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                        <Compass className="h-4 w-4 text-primary" aria-hidden="true" />
                      </div>
                      <div>
                        <p className="font-semibold text-sm">
                          {dest || "Trip Plan"}
                        </p>
                        <p className="text-[10px] text-muted-foreground">
                          Saved {formatDate(trip.saved_at)}
                        </p>
                      </div>
                    </div>

                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive shrink-0"
                      title="Remove saved trip"
                      onClick={() => removeSavedTrip(trip.session_id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>

                  {/* Trip meta badges */}
                  <div className="flex flex-wrap gap-1.5">
                    {days && (
                      <Badge variant="outline" className="text-[11px] px-1.5 py-0 h-5">
                        <Calendar className="h-2.5 w-2.5 mr-1" />
                        {days} days
                      </Badge>
                    )}
                    {budget && (
                      <Badge variant="secondary" className="text-[11px] px-1.5 py-0 h-5">
                        <DollarSign className="h-2.5 w-2.5 mr-1" />
                        ₹{Number(budget).toLocaleString("en-IN")}
                      </Badge>
                    )}
                  </div>

                  {/* Resume button */}
                  <Button
                    size="sm"
                    className="w-full text-xs flex items-center justify-center gap-1 mt-auto"
                    onClick={() => resumeTrip(trip)}
                  >
                    Resume Trip <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </Card>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
};

export default Favorites;
