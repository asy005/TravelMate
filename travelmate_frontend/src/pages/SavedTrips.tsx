/**
 * Saved Trips Page (/saved-trips)
 *
 * Dedicated page displaying customized travel plans, interactive itineraries,
 * route-optimized stops, and smart packing checklists.
 *
 * Integrates directly with the database-backed SavedTrip API (/saved-trips)
 * when authenticated, and falls back to browser-local storage for offline/guest sessions.
 */
import { useContext, useEffect, useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { AuthContext } from "@/hooks/AuthContext";
import { Navigation } from "@/components/Navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  BookmarkCheck,
  Calendar,
  Compass,
  MapPin,
  Trash2,
  ArrowRight,
  Route,
  Sparkles,
  CheckCircle2,
  Backpack,
  Cloud,
  HardDrive,
  Search,
  Plus,
  Info,
  Clock,
  ExternalLink,
  MessageSquare,
  Heart,
} from "lucide-react";
import {
  getSavedTrips,
  deleteSavedTrip,
  resolveImageUrl,
  SavedTrip as DBSavedTrip,
} from "@/lib/api";

const SAVED_TRIPS_KEY = "travelmate_saved_trips";
const DEFAULT_TRIP_COVER =
  "https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&q=80&w=800";

interface LocalChatTrip {
  session_id: string;
  plan: any;
  saved_at: string;
  destination?: string;
}

function loadLocalTrips(): any[] {
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

export const SavedTrips = () => {
  const { token } = useContext(AuthContext);
  const navigate = useNavigate();

  // State
  const [dbTrips, setDbTrips] = useState<DBSavedTrip[]>([]);
  const [localTrips, setLocalTrips] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"all" | "customized" | "ai_chat">("all");

  // Deletion modal state
  const [tripToDelete, setTripToDelete] = useState<{
    id?: number;
    sessionId?: string;
    destId?: number | string;
    destName?: string;
    title: string;
  } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Load trips from API and localStorage
  const fetchTrips = useCallback(async () => {
    setLoading(true);
    const local = loadLocalTrips();
    setLocalTrips(local);

    if (token) {
      try {
        const remote = await getSavedTrips();
        if (Array.isArray(remote)) {
          setDbTrips(remote);
        }
      } catch (err) {
        console.warn("Could not load database saved trips:", err);
      }
    } else {
      setDbTrips([]);
    }
    setLoading(false);
  }, [token]);

  useEffect(() => {
    fetchTrips();
  }, [fetchTrips]);

  // Handle trip deletion
  const confirmDelete = async () => {
    if (!tripToDelete) return;
    setIsDeleting(true);

    try {
      // 1. Delete from backend if it is a DB trip
      if (tripToDelete.id) {
        await deleteSavedTrip(tripToDelete.id);
        setDbTrips((prev) => prev.filter((t) => t.id !== tripToDelete.id));
      }

      // 2. Remove from local storage
      const currentLocal = loadLocalTrips();
      const updatedLocal = currentLocal.filter((t: any) => {
        if (tripToDelete.id && t.id === tripToDelete.id) return false;
        if (tripToDelete.sessionId && t.session_id === tripToDelete.sessionId) return false;
        if (
          tripToDelete.destId &&
          t.destination_id &&
          String(t.destination_id) === String(tripToDelete.destId)
        )
          return false;
        if (
          tripToDelete.destName &&
          (t.destination_name || t.destination) &&
          (t.destination_name || t.destination).toLowerCase() === tripToDelete.destName.toLowerCase()
        )
          return false;
        if (
          !tripToDelete.destName &&
          t.destination_name &&
          tripToDelete.title &&
          tripToDelete.title.toLowerCase().includes(t.destination_name.toLowerCase())
        )
          return false;
        return true;
      });

      localStorage.setItem(SAVED_TRIPS_KEY, JSON.stringify(updatedLocal));
      setLocalTrips(updatedLocal);
    } catch (err) {
      console.error("Failed to delete trip:", err);
    } finally {
      setIsDeleting(false);
      setTripToDelete(null);
    }
  };

  // Resume an AI assistant chat trip
  const resumeAssistantTrip = (trip: LocalChatTrip) => {
    localStorage.setItem("travelmate_assistant_session", trip.session_id);
    navigate("/");
    setTimeout(() => {
      document.getElementById("trip-chat-input")?.focus();
    }, 400);
  };

  // Combine and deduplicate customized destination trips vs AI chat trips
  // If user has a DB trip for a destination, prefer the DB trip over a local duplicate
  const customizedTrips = useMemo(() => {
    const list: Array<{
      source: "db" | "local";
      data: DBSavedTrip;
    }> = [];

    const dbDestKeys = new Set<string>();

    dbTrips.forEach((t) => {
      const key = (t.destination_name || "").toLowerCase();
      if (key) dbDestKeys.add(key);
      list.push({ source: "db", data: t });
    });

    localTrips.forEach((lt) => {
      // If it looks like a customized trip (has destination_data or itinerary or destination_id)
      if (lt.destination_data || lt.itinerary || lt.destination_id || lt.packing_checklist) {
        const key = (lt.destination_name || lt.destination || "").toLowerCase();
        if (!key || !dbDestKeys.has(key)) {
          list.push({
            source: "local",
            data: {
              id: undefined,
              destination_id: lt.destination_id,
              destination_name: lt.destination_name || lt.destination || "Custom Destination",
              trip_title: lt.trip_title || `Trip to ${lt.destination_name || lt.destination}`,
              trip_duration_days: lt.trip_duration_days || 3,
              destination_data: lt.destination_data,
              itinerary: lt.itinerary,
              selected_activities: lt.selected_activities,
              route_stops: lt.route_stops,
              packing_checklist: lt.packing_checklist,
              custom_packing_items: lt.custom_packing_items,
              notes: lt.notes,
              updated_at: lt.updated_at || lt.saved_at,
            },
          });
        }
      }
    });

    return list;
  }, [dbTrips, localTrips]);

  // AI assistant chat trips
  const assistantTrips: LocalChatTrip[] = useMemo(() => {
    return localTrips.filter((t) => t.session_id && t.plan && !t.destination_data);
  }, [localTrips]);

  // Filtered customized trips based on search query
  const filteredCustomized = useMemo(() => {
    if (!searchQuery.trim()) return customizedTrips;
    const q = searchQuery.toLowerCase();
    return customizedTrips.filter(({ data }) => {
      const title = (data.trip_title || "").toLowerCase();
      const dest = (data.destination_name || "").toLowerCase();
      const notes = (data.notes || "").toLowerCase();
      return title.includes(q) || dest.includes(q) || notes.includes(q);
    });
  }, [customizedTrips, searchQuery]);

  // Filtered assistant trips based on search query
  const filteredAssistant = useMemo(() => {
    if (!searchQuery.trim()) return assistantTrips;
    const q = searchQuery.toLowerCase();
    return assistantTrips.filter((t) => {
      const dest = (t.destination || t.plan?.destination || "").toLowerCase();
      return dest.includes(q);
    });
  }, [assistantTrips, searchQuery]);

  const totalTripsCount = customizedTrips.length + assistantTrips.length;

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navigation />

      <main className="flex-1 container mx-auto px-4 sm:px-6 max-w-7xl pt-28 pb-20 space-y-8 animate-fade-up">
        {/* ── Page Header ── */}
        <div className="bg-card rounded-3xl p-6 sm:p-8 border border-border/60 shadow-sm relative overflow-hidden">
          <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="flex items-start gap-4">
              <div className="h-14 w-14 rounded-2xl bg-primary/10 text-primary flex items-center justify-center shrink-0 shadow-inner">
                <BookmarkCheck className="h-7 w-7 text-primary" aria-hidden="true" />
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center gap-3 flex-wrap">
                  <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground">
                    Saved Trips &amp; Itineraries
                  </h1>
                  <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-semibold">
                    {totalTripsCount} {totalTripsCount === 1 ? "Trip" : "Trips"}
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
                      <HardDrive className="h-3 w-3" /> Device Only
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
                  Review and resume your customized travel plans. Reopen daily itineraries, inspect route-optimized stops, and track your smart packing checklist.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 self-start md:self-auto flex-wrap">
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate("/favorites")}
                className="text-xs font-medium h-9 px-3 gap-1.5 border-border hover:bg-muted"
              >
                <Heart className="h-4 w-4 text-coral" />
                View Favorite Places
              </Button>
              <Button
                size="sm"
                onClick={() => navigate("/#recommendations-section")}
                className="text-xs font-semibold h-9 px-4 gap-1.5 shadow-sm"
              >
                <Plus className="h-4 w-4" />
                Plan New Trip
              </Button>
            </div>
          </div>

          {/* Sync status info banner */}
          {token ? (
            <div className="mt-6 pt-4 border-t border-border/50 flex items-center gap-2 text-xs text-muted-foreground">
              <Info className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
              <span>
                Your customized destination trips are securely backed up to your TravelMate account. Changes made on any device automatically update here.
              </span>
            </div>
          ) : (
            <div className="mt-6 pt-4 border-t border-border/50 flex items-center gap-2 text-xs text-muted-foreground">
              <Info className="h-4 w-4 text-amber-500 shrink-0" />
              <span>
                Trips are currently stored in <strong>this browser only</strong>.{" "}
                <button
                  onClick={() => navigate("/login")}
                  className="font-semibold text-primary underline hover:text-primary/80"
                >
                  Sign in
                </button>{" "}
                to sync and back up your customized plans across all devices.
              </span>
            </div>
          )}
        </div>

        {/* ── Search & Filter Controls (Shown when trips exist) ── */}
        {totalTripsCount > 0 && (
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search by trip title, destination, or notes..."
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

            {assistantTrips.length > 0 && (
              <div className="flex items-center gap-1.5 self-start sm:self-auto">
                <Button
                  variant={activeTab === "all" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActiveTab("all")}
                  className="text-xs h-8 px-3 rounded-full"
                >
                  All ({totalTripsCount})
                </Button>
                <Button
                  variant={activeTab === "customized" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActiveTab("customized")}
                  className="text-xs h-8 px-3 rounded-full"
                >
                  Destination Plans ({customizedTrips.length})
                </Button>
                <Button
                  variant={activeTab === "ai_chat" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActiveTab("ai_chat")}
                  className="text-xs h-8 px-3 rounded-full"
                >
                  AI Chat Plans ({assistantTrips.length})
                </Button>
              </div>
            )}
          </div>
        )}

        {/* ── Content Grid or Empty States ── */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" aria-busy="true">
            {[...Array(6)].map((_, i) => (
              <Card key={i} className="overflow-hidden rounded-2xl border border-border/60 p-0">
                <Skeleton className="h-44 w-full" />
                <div className="p-5 space-y-3">
                  <Skeleton className="h-5 w-3/4" />
                  <Skeleton className="h-4 w-1/2" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-9 w-full rounded-xl" />
                </div>
              </Card>
            ))}
          </div>
        ) : totalTripsCount === 0 ? (
          <div className="bg-card rounded-3xl p-8 sm:p-12 border border-border/60 text-center shadow-sm">
            <EmptyState
              icon={Calendar}
              title="No saved trips yet"
              description="Customize your travel plans! Open any destination to build personalized day-by-day itineraries, add route stops, and check off items in your packing checklist."
              actionLabel="Explore Destinations & Plan a Trip"
              onAction={() => navigate("/#recommendations-section")}
            />
          </div>
        ) : (
          <div className="space-y-8">
            {/* 1. Customized Destination Trips */}
            {(activeTab === "all" || activeTab === "customized") && filteredCustomized.length > 0 && (
              <div className="space-y-4">
                {activeTab === "all" && assistantTrips.length > 0 && (
                  <h2 className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                    <Compass className="h-4 w-4 text-primary" />
                    Customized Destination Itineraries ({filteredCustomized.length})
                  </h2>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                  {filteredCustomized.map(({ source, data }) => {
                    const checklist = data.packing_checklist || {};
                    const customItems = data.custom_packing_items || [];
                    const allKeys = Array.from(new Set([...Object.keys(checklist), ...customItems]));
                    const packedCount = allKeys.filter((k) => !!checklist[k]).length;
                    const totalItems = allKeys.length;
                    const packedPct =
                      totalItems > 0 ? Math.round((packedCount / totalItems) * 100) : 0;

                    const heroImg =
                      resolveImageUrl(
                        data.destination_data?.image || data.destination_data?.thumbnail_url
                      ) || DEFAULT_TRIP_COVER;

                    const destTarget =
                      data.destination_id || encodeURIComponent(data.destination_name);

                    const stopsCount = Array.isArray(data.route_stops)
                      ? data.route_stops.length
                      : 0;

                    const activitiesCount = Array.isArray(data.selected_activities)
                      ? data.selected_activities.length
                      : 0;

                    const itineraryDays = data.itinerary
                      ? Object.keys(data.itinerary).length
                      : 0;

                    return (
                      <Card
                        key={data.id ? `db-${data.id}` : `local-${data.destination_name}`}
                        className="group overflow-hidden rounded-2xl bg-card border border-border/60 hover:border-primary/40 shadow-sm hover:shadow-md transition-all duration-300 flex flex-col h-full"
                      >
                        {/* Cover image strip */}
                        <div className="relative h-44 w-full overflow-hidden bg-muted">
                          <img
                            src={heroImg}
                            alt={data.destination_name}
                            loading="lazy"
                            onError={(e) => {
                              (e.target as HTMLImageElement).src = DEFAULT_TRIP_COVER;
                            }}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                          />
                          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/25 to-transparent" />

                          {/* Top storage status badge */}
                          <div className="absolute top-3 left-3">
                            {source === "db" ? (
                              <Badge className="bg-emerald-600/90 text-white border-0 text-[10px] font-semibold flex items-center gap-1 shadow-sm backdrop-blur-md">
                                <Cloud className="h-3 w-3" /> Cloud Synced
                              </Badge>
                            ) : (
                              <Badge className="bg-amber-600/90 text-white border-0 text-[10px] font-semibold flex items-center gap-1 shadow-sm backdrop-blur-md">
                                <HardDrive className="h-3 w-3" /> Device Only
                              </Badge>
                            )}
                          </div>

                          {/* Delete trip button */}
                          <button
                            onClick={() =>
                              setTripToDelete({
                                id: data.id,
                                destId: data.destination_id || undefined,
                                destName: data.destination_name,
                                title: data.trip_title || data.destination_name,
                              })
                            }
                            className="absolute top-3 right-3 h-8 w-8 rounded-full bg-background/85 backdrop-blur-md flex items-center justify-center text-muted-foreground hover:text-destructive hover:bg-background transition-colors shadow-sm"
                            title="Delete saved trip"
                            aria-label={`Delete trip to ${data.destination_name}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>

                          {/* Destination Title on Image */}
                          <div className="absolute bottom-3 left-3 right-3">
                            <h3 className="text-base font-bold text-white drop-shadow-sm truncate">
                              {data.trip_title || `Trip to ${data.destination_name}`}
                            </h3>
                            <p className="text-xs text-white/85 flex items-center gap-1 drop-shadow-sm truncate">
                              <MapPin className="h-3 w-3 text-coral shrink-0" />
                              <span>{data.destination_name}</span>
                            </p>
                          </div>
                        </div>

                        {/* Card Details */}
                        <div className="p-4 sm:p-5 flex-1 flex flex-col justify-between gap-4">
                          <div className="space-y-3">
                            {/* Metadata Badges */}
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <Badge
                                variant="outline"
                                className="text-[11px] px-2 py-0.5 h-5 font-medium border-border/80"
                              >
                                <Calendar className="h-3 w-3 text-primary mr-1" />
                                {data.trip_duration_days || 3} Days
                              </Badge>

                              {stopsCount > 0 && (
                                <Badge
                                  variant="outline"
                                  className="text-[11px] px-2 py-0.5 h-5 font-medium border-border/80"
                                >
                                  <Route className="h-3 w-3 text-sky-500 mr-1" />
                                  {stopsCount} {stopsCount === 1 ? "Stop" : "Stops"}
                                </Badge>
                              )}

                              {activitiesCount > 0 && (
                                <Badge
                                  variant="outline"
                                  className="text-[11px] px-2 py-0.5 h-5 font-medium border-border/80"
                                >
                                  <Sparkles className="h-3 w-3 text-amber-500 mr-1" />
                                  {activitiesCount} Activities
                                </Badge>
                              )}

                              {itineraryDays > 0 && (
                                <Badge
                                  variant="secondary"
                                  className="text-[11px] px-2 py-0.5 h-5 font-medium"
                                >
                                  {itineraryDays} Day Plan
                                </Badge>
                              )}
                            </div>

                            {/* Packing Progress Bar */}
                            {totalItems > 0 && (
                              <div className="space-y-1.5 bg-muted/30 p-2.5 rounded-xl border border-border/40">
                                <div className="flex items-center justify-between text-xs">
                                  <span className="font-medium text-foreground flex items-center gap-1">
                                    <Backpack className="h-3.5 w-3.5 text-coral" />
                                    Packing Checklist
                                  </span>
                                  <span className="text-[11px] font-semibold text-muted-foreground">
                                    {packedCount}/{totalItems} ({packedPct}%)
                                  </span>
                                </div>
                                <Progress value={packedPct} className="h-1.5 bg-muted" />
                              </div>
                            )}

                            {/* Notes Snippet */}
                            {data.notes && (
                              <p className="text-xs text-muted-foreground bg-muted/20 p-2.5 rounded-xl border border-border/40 italic line-clamp-2">
                                "{data.notes}"
                              </p>
                            )}

                            {data.updated_at && (
                              <p className="text-[10px] text-muted-foreground flex items-center gap-1">
                                <Clock className="h-2.5 w-2.5" />
                                Last saved {formatDate(data.updated_at)}
                              </p>
                            )}
                          </div>

                          {/* Footer Action */}
                          <div className="pt-3 border-t border-border/50">
                            <Button
                              size="sm"
                              onClick={() => navigate(`/destination/${destTarget}`)}
                              className="w-full text-xs font-semibold h-8 rounded-xl flex items-center justify-center gap-1.5 shadow-sm"
                            >
                              <span>Resume &amp; Customize Trip</span>
                              <ArrowRight className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </div>
                      </Card>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 2. AI Assistant Chat Trips */}
            {(activeTab === "all" || activeTab === "ai_chat") && filteredAssistant.length > 0 && (
              <div className="space-y-4 pt-4">
                <h2 className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 text-primary" />
                  AI Assistant Itinerary Sessions ({filteredAssistant.length})
                </h2>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                  {filteredAssistant.map((trip) => {
                    const dest =
                      trip.destination ||
                      trip.plan?.destination ||
                      trip.plan?.trip?.destination ||
                      trip.plan?.trip_overview?.primary_destination ||
                      "Travel Plan";
                    const days =
                      trip.plan?.duration_days ||
                      trip.plan?.trip?.duration_days ||
                      trip.plan?.duration ||
                      trip.plan?.trip_overview?.duration_days ||
                      3;
                    const budget =
                      trip.plan?.budget ||
                      trip.plan?.trip?.budget ||
                      trip.plan?.trip_overview?.budget;

                    return (
                      <Card
                        key={trip.session_id}
                        className="group overflow-hidden rounded-2xl bg-card border border-border/60 hover:border-primary/40 shadow-sm hover:shadow-md transition-all duration-300 flex flex-col h-full"
                      >
                        <div className="p-5 flex-1 flex flex-col justify-between gap-4">
                          <div className="space-y-3">
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex items-center gap-2.5">
                                <div className="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
                                  <MessageSquare className="h-5 w-5" />
                                </div>
                                <div>
                                  <h3 className="text-sm font-bold text-foreground">{dest}</h3>
                                  <p className="text-[10px] text-muted-foreground">
                                    Saved {formatDate(trip.saved_at)}
                                  </p>
                                </div>
                              </div>

                              <button
                                onClick={() =>
                                  setTripToDelete({
                                    sessionId: trip.session_id,
                                    destName: dest,
                                    title: `AI Plan for ${dest}`,
                                  })
                                }
                                className="h-7 w-7 rounded-full flex items-center justify-center text-muted-foreground hover:text-destructive transition-colors"
                                title="Delete session"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>

                            <div className="flex items-center gap-1.5 flex-wrap">
                              <Badge variant="outline" className="text-[11px] px-2 py-0.5 h-5 font-medium">
                                <Calendar className="h-2.5 w-2.5 mr-1" />
                                {days} Days
                              </Badge>

                              {budget && (
                                <Badge variant="secondary" className="text-[11px] px-2 py-0.5 h-5 font-medium">
                                  ₹{Number(budget).toLocaleString("en-IN")}
                                </Badge>
                              )}

                              <Badge
                                variant="outline"
                                className="text-[10px] border-amber-500/40 text-amber-600 dark:text-amber-400 bg-amber-500/5"
                              >
                                Device Session
                              </Badge>
                            </div>
                          </div>

                          <div className="pt-3 border-t border-border/50">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => resumeAssistantTrip(trip)}
                              className="w-full text-xs font-semibold h-8 rounded-xl flex items-center justify-center gap-1.5 hover:bg-primary hover:text-primary-foreground"
                            >
                              <span>Continue Chat Session</span>
                              <ArrowRight className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </div>
                      </Card>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* ── Delete Confirmation Dialog ── */}
      <AlertDialog open={!!tripToDelete} onOpenChange={(open) => !open && setTripToDelete(null)}>
        <AlertDialogContent className="rounded-2xl max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-lg font-bold">
              Delete Saved Trip?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-xs text-muted-foreground leading-relaxed">
              Are you sure you want to remove{" "}
              <strong className="text-foreground">{tripToDelete?.title}</strong>? This will permanently erase the customized itinerary, route stops, and packing checklist for this trip.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="gap-2 sm:gap-0">
            <AlertDialogCancel disabled={isDeleting} className="text-xs h-9 rounded-xl">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={isDeleting}
              onClick={confirmDelete}
              className="text-xs h-9 rounded-xl bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? "Deleting..." : "Delete Trip"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default SavedTrips;
