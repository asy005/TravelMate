import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  Loader2,
  ExternalLink,
  AlertTriangle,
  ArrowLeft,
  Cloud,
  Wind,
  Sun,
  MapPin,
  RefreshCcw,
  Compass,
  Calendar,
  Clock,
  Sparkles,
  Ticket,
  Activity,
  DollarSign,
  Layers,
  Star,
  CheckCircle2,
  MessageCircle,
  Utensils,
  Bookmark,
  BookmarkCheck,
  Check,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

import { ReviewsSection } from "@/components/ReviewsSection";
import { PackingListBox } from "@/components/PackingListBox";
import { RouteOptimizerBox, Point } from "@/components/RouteOptimizerBox";
import { SmartItineraryBox } from "@/components/SmartItineraryBox";
import { LanguageSelector, getStoredLanguage } from "@/components/LanguageSelector";
import {
  translateText,
  getDestinationById,
  resolveImageUrl,
  saveTrip,
  getSavedTripByDestination,
  SavedTrip,
} from "@/lib/api";
import { DESTINATIONS } from "@/data/destinations";

const WEATHER_CODE_MAP: Record<number, { label: string; icon: string }> = {
  0: { label: "Clear sky", icon: "☀️" },
  1: { label: "Mainly clear", icon: "🌤️" },
  2: { label: "Partly cloudy", icon: "⛅" },
  3: { label: "Overcast", icon: "☁️" },
  45: { label: "Foggy", icon: "🌫️" },
  48: { label: "Depositing rime fog", icon: "🌫️" },
  51: { label: "Light drizzle", icon: "🌦️" },
  53: { label: "Moderate drizzle", icon: "🌦️" },
  55: { label: "Dense drizzle", icon: "🌧️" },
  61: { label: "Slight rain", icon: "🌧️" },
  63: { label: "Moderate rain", icon: "🌧️" },
  65: { label: "Heavy rain", icon: "🌧️" },
  71: { label: "Slight snow", icon: "🌨️" },
  73: { label: "Moderate snow", icon: "🌨️" },
  75: { label: "Heavy snow", icon: "❄️" },
  80: { label: "Slight rain showers", icon: "🌦️" },
  81: { label: "Moderate rain showers", icon: "🌧️" },
  82: { label: "Violent rain showers", icon: "⛈️" },
  95: { label: "Thunderstorm", icon: "⛈️" },
  96: { label: "Thunderstorm with slight hail", icon: "⛈️" },
  99: { label: "Thunderstorm with heavy hail", icon: "⛈️" },
};

const DEFAULT_IMAGE =
  "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&q=80&w=1200";

const DestinationPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [destination, setDestination] = useState<any>(null);
  const [weather, setWeather] = useState<any>(null);
  const [dailyForecast, setDailyForecast] = useState<any>(null);
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [weatherError, setWeatherError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [descLang, setDescLang] = useState<string>(getStoredLanguage());
  const [translatedDesc, setTranslatedDesc] = useState<string | null>(null);
  const [isTranslatingDesc, setIsTranslatingDesc] = useState(false);
  const [activeImage, setActiveImage] = useState<string>(DEFAULT_IMAGE);

  // Saved trip states
  const [savedTripId, setSavedTripId] = useState<number | null>(null);
  const [isSaved, setIsSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatusMsg, setSaveStatusMsg] = useState<string | null>(null);

  // User customizations to persist
  const [selectedActivities, setSelectedActivities] = useState<any[]>([]);
  const [packingState, setPackingState] = useState<{
    packingList: string[];
    packedItems: Record<string, boolean>;
    customItems: string[];
  }>({ packingList: [], packedItems: {}, customItems: [] });
  const [itineraryPlan, setItineraryPlan] = useState<Record<string, string[]> | null>(null);
  const [itineraryDays, setItineraryDays] = useState(3);
  const [routeStops, setRouteStops] = useState<Point[]>([]);
  const [userNotes, setUserNotes] = useState("");

  const fetchWeather = async (lat: number, lon: number) => {
    setWeatherLoading(true);
    setWeatherError(null);
    try {
      const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=auto`;
      const res = await axios.get(url, { timeout: 8000 });
      setWeather(res.data?.current_weather || null);
      setDailyForecast(res.data?.daily || null);
    } catch (err: any) {
      console.warn("Weather fetch failed:", err);
      setWeatherError("Weather service temporarily unreachable. Click retry to update.");
      setWeather(null);
      setDailyForecast(null);
    } finally {
      setWeatherLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    const loadData = async () => {
      let foundDest: any = null;
      const decodedId = id ? decodeURIComponent(id) : "";

      try {
        const landmarkSaved = localStorage.getItem("travelmate_landmark_history");
        if (landmarkSaved) {
          const landmarkList = JSON.parse(landmarkSaved);
          foundDest = landmarkList.find(
            (d: any) =>
              String(d.id) === id ||
              String(d.id) === decodedId ||
              (d.name && String(d.name).toLowerCase() === decodedId.toLowerCase())
          );
        }
      } catch {}

      if (!foundDest) {
        foundDest = DESTINATIONS.find(
          (d) =>
            String(d.id) === id ||
            String(d.id) === decodedId ||
            d.name.toLowerCase() === decodedId.toLowerCase()
        );
      }

      if (!foundDest) {
        try {
          const recSaved = localStorage.getItem("travelmate_recommendations");
          if (recSaved) {
            const parsed = JSON.parse(recSaved);
            foundDest = (parsed.destinations || []).find(
              (d: any) =>
                String(d.id) === id ||
                String(d.id) === decodedId ||
                (d.name && d.name.toLowerCase() === decodedId.toLowerCase())
            );
          }
        } catch {}
      }

      if (!foundDest) {
        try {
          const localTrips: any[] = JSON.parse(
            localStorage.getItem("travelmate_saved_trips") || "[]"
          );
          const savedMatch = localTrips.find(
            (t: any) =>
              String(t.destination_id) === id ||
              String(t.destination_id) === decodedId ||
              (t.destination_name &&
                t.destination_name.toLowerCase() === decodedId.toLowerCase()) ||
              (t.destination && t.destination.toLowerCase() === decodedId.toLowerCase())
          );
          if (savedMatch && savedMatch.destination_data) {
            foundDest = { ...savedMatch.destination_data };
          }
        } catch {}
      }

      try {
        if (id) {
          const apiData = await getDestinationById(id);
          if (apiData && isMounted) {
            foundDest = { ...foundDest, ...apiData };
          }
        }
      } catch {
      }

      if (!isMounted) return;

      if (foundDest) {
        setDestination(foundDest);
        const resolvedHero =
          resolveImageUrl(foundDest.image || foundDest.thumbnail_url) || DEFAULT_IMAGE;
        setActiveImage(resolvedHero);
        setLoading(false);

        if (foundDest.lat && foundDest.lon) {
          fetchWeather(foundDest.lat, foundDest.lon);
        }

        // Try restoring saved trip if one exists
        try {
          const token = localStorage.getItem("travelmate_token") || localStorage.getItem("access_token");
          let existingTrip: SavedTrip | null = null;
          if (token && foundDest.id) {
            existingTrip = await getSavedTripByDestination(foundDest.id);
          }
          if (!existingTrip) {
            try {
              const localTrips: any[] = JSON.parse(localStorage.getItem("travelmate_saved_trips") || "[]");
              existingTrip = localTrips.find(
                (t: any) =>
                  (t.destination_id && String(t.destination_id) === String(foundDest.id)) ||
                  (t.destination_name && t.destination_name.toLowerCase() === foundDest.name.toLowerCase()) ||
                  (t.destination && t.destination.toLowerCase() === foundDest.name.toLowerCase())
              ) || null;
            } catch {}
          }

          if (existingTrip && isMounted) {
            setSavedTripId(existingTrip.id || null);
            setIsSaved(true);
            if (existingTrip.itinerary) {
              setItineraryPlan(existingTrip.itinerary);
            }
            if (existingTrip.trip_duration_days) {
              setItineraryDays(existingTrip.trip_duration_days);
            }
            if (existingTrip.route_stops && Array.isArray(existingTrip.route_stops)) {
              setRouteStops(existingTrip.route_stops);
            }
            if (existingTrip.selected_activities && Array.isArray(existingTrip.selected_activities)) {
              setSelectedActivities(existingTrip.selected_activities);
            }
            if (existingTrip.packing_checklist || existingTrip.custom_packing_items) {
              setPackingState({
                packingList: [],
                packedItems: existingTrip.packing_checklist || {},
                customItems: existingTrip.custom_packing_items || [],
              });
            }
            if (existingTrip.notes) {
              setUserNotes(existingTrip.notes);
            }
          }
        } catch (err) {
          console.warn("Notice: Saved trip check completed without saved record:", err);
        }
      } else {
        setDestination(null);
        setLoading(false);
      }
    };

    loadData();

    return () => {
      isMounted = false;
    };
  }, [id]);

  const handleSaveTrip = async () => {
    if (!destination) return;
    setIsSaving(true);
    setSaveStatusMsg(null);

    const token = localStorage.getItem("travelmate_token") || localStorage.getItem("access_token");
    const destId = Number(destination.id) || null;
    const destName = destination.name;

    const payload: SavedTrip = {
      id: savedTripId || undefined,
      destination_id: destId,
      destination_name: destName,
      trip_title: `Custom Trip to ${destName}`,
      trip_duration_days: itineraryDays || Number(destination.ideal_duration) || 3,
      destination_data: {
        id: destination.id,
        name: destination.name,
        state: destination.state,
        country: destination.country,
        category: destination.category,
        average_budget: destination.average_budget || destination.budget,
        lat: destination.lat,
        lon: destination.lon,
      },
      itinerary: itineraryPlan,
      selected_attractions: destination.attractions || [],
      selected_activities: selectedActivities,
      route_stops: routeStops,
      packing_checklist: packingState.packedItems,
      custom_packing_items: packingState.customItems,
      trip_preferences: {
        climate: weather?.temperature ? `${weather.temperature}°C` : "moderate",
        duration: itineraryDays,
      },
      notes: userNotes || null,
    };

    if (token) {
      try {
        const saved = await saveTrip(payload);
        if (saved) {
          setSavedTripId(saved.id || null);
          setIsSaved(true);
          setSaveStatusMsg("Trip saved to your account!");
          setTimeout(() => setSaveStatusMsg(null), 4000);
        }
      } catch (err: any) {
        console.error("Save error:", err);
        saveLocalTrip(payload);
        setIsSaved(true);
        setSaveStatusMsg("Saved locally to device!");
        setTimeout(() => setSaveStatusMsg(null), 4000);
      }
    } else {
      saveLocalTrip(payload);
      setIsSaved(true);
      setSaveStatusMsg("Saved to this device! Log in to sync across devices.");
      setTimeout(() => setSaveStatusMsg(null), 4000);
    }
    setIsSaving(false);
  };

  const saveLocalTrip = (tripPayload: SavedTrip) => {
    try {
      const savedTrips: any[] = JSON.parse(localStorage.getItem("travelmate_saved_trips") || "[]");
      const existingIdx = savedTrips.findIndex(
        (t: any) =>
          (t.destination_id && String(t.destination_id) === String(tripPayload.destination_id)) ||
          (t.destination_name && t.destination_name.toLowerCase() === tripPayload.destination_name.toLowerCase())
      );
      if (existingIdx >= 0) {
        savedTrips[existingIdx] = { ...savedTrips[existingIdx], ...tripPayload, updated_at: new Date().toISOString() };
      } else {
        savedTrips.push({
          session_id: `local_trip_${Date.now()}`,
          ...tripPayload,
          saved_at: new Date().toISOString(),
        });
      }
      localStorage.setItem("travelmate_saved_trips", JSON.stringify(savedTrips));
    } catch {}
  };

  const toggleActivitySelection = (act: any) => {
    setSelectedActivities((prev) => {
      const exists = prev.some((a) => (a.id && a.id === act.id) || a.name === act.name);
      if (exists) {
        return prev.filter((a) => (a.id && a.id !== act.id) || a.name !== act.name);
      } else {
        return [...prev, act];
      }
    });
  };

  const handleDescLangChange = async (newLang: string) => {
    setDescLang(newLang);
    if (newLang === "en" || !destination?.description) {
      setTranslatedDesc(null);
      return;
    }
    setIsTranslatingDesc(true);
    try {
      const res = await translateText(destination.description, newLang);
      if (res.translated_text) {
        setTranslatedDesc(res.translated_text);
      }
    } catch {
    } finally {
      setIsTranslatingDesc(false);
    }
  };

  const handlePlanTrip = () => {
    navigate(`/chat?destination=${encodeURIComponent(destination?.name || "")}`);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-muted-foreground text-sm font-medium">Loading destination guide...</p>
      </div>
    );
  }

  if (!destination) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-background p-6 text-center">
        <div className="h-14 w-14 rounded-full bg-muted flex items-center justify-center text-muted-foreground">
          <AlertTriangle className="h-7 w-7 text-amber-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-foreground">Destination Not Found</h1>
          <p className="text-muted-foreground text-sm max-w-md mt-1">
            We couldn't locate details for this destination. It may have been removed or the link is invalid.
          </p>
        </div>
        <Button onClick={() => navigate("/")} className="mt-2 flex items-center gap-2">
          <ArrowLeft className="h-4 w-4" /> Back to Explore
        </Button>
      </div>
    );
  }

  const weatherInfo = weather ? WEATHER_CODE_MAP[weather.weathercode] : null;
  const attractions = Array.isArray(destination.attractions) ? destination.attractions : [];
  const activities = Array.isArray(destination.activities) ? destination.activities : [];
  const restaurants = Array.isArray(destination.restaurants) ? destination.restaurants : [];

  const categoryName = destination.category || destination.type || "Attraction";
  const stateDisplay = destination.state || destination.region || "";
  const locationLabel = [destination.city, stateDisplay, destination.country || "India"]
    .filter(Boolean)
    .join(", ");

  const bestSeasonText = destination.best_season || "October - March";
  const durationText = destination.ideal_duration ? `${destination.ideal_duration} Days` : "3 - 5 Days";
  const budgetText = destination.average_budget
    ? `₹${Math.round(Number(destination.average_budget)).toLocaleString("en-IN")}`
    : "₹2,500";

  return (
    <div className="min-h-screen bg-background">
      {/* Top Navigation Bar */}
      <div className="sticky top-0 z-40 bg-background/80 backdrop-blur-md border-b border-border/50 px-6 py-3">
        <div className="container mx-auto flex items-center justify-between gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(-1)}
            className="text-xs h-8 flex items-center gap-1.5"
          >
            <ArrowLeft className="h-4 w-4" /> Back
          </Button>

          <span className="font-semibold text-sm truncate hidden sm:inline max-w-xs">
            {destination.name}
          </span>

          <div className="flex items-center gap-2">
            {isSaved && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate("/saved-trips")}
                className="text-xs h-8 text-primary hover:text-primary/80 flex items-center gap-1.5"
                title="Open Saved Trips"
              >
                <BookmarkCheck className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Saved Trips</span>
              </Button>
            )}

            <Button
              size="sm"
              variant={isSaved ? "outline" : "default"}
              onClick={handleSaveTrip}
              disabled={isSaving}
              className={`text-xs h-8 flex items-center gap-1.5 font-medium transition-all ${
                isSaved
                  ? "border-emerald-500/50 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20"
                  : ""
              }`}
            >
              {isSaving ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                  <span>Saving...</span>
                </>
              ) : isSaved ? (
                <>
                  <Check className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 mr-1" />
                  <span>Trip Saved ✓</span>
                </>
              ) : (
                <>
                  <Bookmark className="h-3.5 w-3.5 mr-1" />
                  <span>Save Trip</span>
                </>
              )}
            </Button>

            <Button
              size="sm"
              onClick={handlePlanTrip}
              className="text-xs h-8 flex items-center gap-1.5 font-medium"
            >
              <Compass className="h-3.5 w-3.5" /> Plan Trip Here
            </Button>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 sm:px-6 py-8 max-w-5xl space-y-8 animate-fade-up">
        {/* Title Header */}
        <div className="space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
                  {destination.name}
                </h1>
                <Badge variant="secondary" className="text-xs py-0.5 px-2.5 font-medium">
                  {categoryName}
                </Badge>
                {destination.mood && (
                  <Badge variant="default" className="text-xs py-0.5 px-2.5 font-medium">
                    {destination.mood}
                  </Badge>
                )}
              </div>
              <p className="text-sm text-muted-foreground flex items-center gap-1.5 font-medium">
                <MapPin className="h-4 w-4 text-coral shrink-0" />
                <span>{locationLabel}</span>
              </p>
            </div>

            <Button
              size="lg"
              onClick={handlePlanTrip}
              className="text-sm font-semibold shadow-sm flex items-center gap-2 px-5"
            >
              <Compass className="h-4 w-4" /> Plan a Trip to {destination.name}
            </Button>
          </div>
        </div>

        {/* Hero Image Showcase */}
        <div className="space-y-3">
          <div className="w-full h-72 sm:h-96 rounded-2xl overflow-hidden shadow-md border border-border/50 relative bg-muted group">
            <img
              src={activeImage}
              alt={destination.name}
              className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
            <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between text-white">
              <span className="font-semibold text-lg drop-shadow-sm">{destination.name}</span>
              {destination.avg_rating && (
                <span className="bg-black/60 backdrop-blur-sm px-2.5 py-1 rounded-lg flex items-center gap-1 text-xs font-semibold text-amber-300">
                  <Star className="h-3.5 w-3.5 fill-amber-300 text-amber-300" />
                  {Number(destination.avg_rating).toFixed(1)} Rating
                </span>
              )}
            </div>
          </div>

          {/* Attraction Thumbnails Strip if attractions have photos */}
          {attractions.some((a: any) => a.image) && (
            <div className="flex items-center gap-2.5 overflow-x-auto pb-1 scrollbar-none">
              <button
                type="button"
                onClick={() =>
                  setActiveImage(
                    resolveImageUrl(destination.image || destination.thumbnail_url) || DEFAULT_IMAGE
                  )
                }
                className={`relative h-16 w-24 shrink-0 rounded-xl overflow-hidden border-2 transition-all ${
                  activeImage === (resolveImageUrl(destination.image || destination.thumbnail_url) || DEFAULT_IMAGE)
                    ? "border-primary ring-2 ring-primary/20"
                    : "border-border/60 opacity-70 hover:opacity-100"
                }`}
              >
                <img
                  src={resolveImageUrl(destination.image || destination.thumbnail_url) || DEFAULT_IMAGE}
                  alt={destination.name}
                  className="w-full h-full object-cover"
                />
              </button>
              {attractions
                .filter((a: any) => a.image)
                .slice(0, 6)
                .map((a: any) => {
                  const resolved = resolveImageUrl(a.image);
                  return (
                    <button
                      key={a.id}
                      type="button"
                      onClick={() => setActiveImage(resolved)}
                      title={a.name}
                      className={`relative h-16 w-24 shrink-0 rounded-xl overflow-hidden border-2 transition-all ${
                        activeImage === resolved
                          ? "border-primary ring-2 ring-primary/20"
                          : "border-border/60 opacity-70 hover:opacity-100"
                      }`}
                    >
                      <img src={resolved} alt={a.name} className="w-full h-full object-cover" />
                    </button>
                  );
                })}
            </div>
          )}
        </div>

        {/* Quick Travel Information Strip (Overview Cards) */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          <Card className="p-4 bg-card/80 backdrop-blur-md border-border/60 space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
              <Calendar className="h-3.5 w-3.5 text-primary" />
              <span>Best Time to Visit</span>
            </div>
            <p className="text-base font-bold text-foreground">{bestSeasonText}</p>
            <p className="text-[11px] text-muted-foreground">Optimal weather & sights</p>
          </Card>

          <Card className="p-4 bg-card/80 backdrop-blur-md border-border/60 space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
              <Clock className="h-3.5 w-3.5 text-coral" />
              <span>Ideal Duration</span>
            </div>
            <p className="text-base font-bold text-foreground">{durationText}</p>
            <p className="text-[11px] text-muted-foreground">Recommended itinerary</p>
          </Card>

          <Card className="p-4 bg-card/80 backdrop-blur-md border-border/60 space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
              <DollarSign className="h-3.5 w-3.5 text-emerald-500" />
              <span>Est. Daily Budget</span>
            </div>
            <p className="text-base font-bold text-foreground">{budgetText}/day</p>
            <p className="text-[11px] text-muted-foreground">Per person avg. stay & food</p>
          </Card>

          <Card className="p-4 bg-card/80 backdrop-blur-md border-border/60 space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
              <Layers className="h-3.5 w-3.5 text-sky-500" />
              <span>Travel Style</span>
            </div>
            <p className="text-base font-bold text-foreground">{categoryName}</p>
            <p className="text-[11px] text-muted-foreground">
              {destination.mood ? `${destination.mood} vibe` : "Scenic exploration"}
            </p>
          </Card>
        </div>

        {/* Live Weather Forecast Card */}
        <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60">
          <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
            <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
              <Sun className="h-5 w-5 text-amber-500" />
              <span>Current Weather in {destination.name}</span>
            </h2>
            {destination.lat && destination.lon && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => fetchWeather(destination.lat, destination.lon)}
                disabled={weatherLoading}
                className="text-xs h-7 px-2 text-muted-foreground"
              >
                <RefreshCcw className={`h-3 w-3 mr-1 ${weatherLoading ? "animate-spin" : ""}`} />
                Refresh
              </Button>
            )}
          </div>

          {weatherLoading ? (
            <div className="py-4 flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              <span>Loading live meteorological forecast...</span>
            </div>
          ) : weather ? (
            <div className="space-y-4 pt-1">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-muted/40 p-4 rounded-xl border border-border/40 flex items-center gap-3">
                  <span className="text-2xl">{weatherInfo?.icon || "🌤️"}</span>
                  <div>
                    <p className="text-xs text-muted-foreground font-medium">Temperature</p>
                    <p className="text-lg font-bold text-foreground">{weather.temperature}°C</p>
                  </div>
                </div>

                <div className="bg-muted/40 p-4 rounded-xl border border-border/40 flex items-center gap-3">
                  <Wind className="h-6 w-6 text-sky-500" />
                  <div>
                    <p className="text-xs text-muted-foreground font-medium">Wind Speed</p>
                    <p className="text-lg font-bold text-foreground">{weather.windspeed} km/h</p>
                  </div>
                </div>

                <div className="bg-muted/40 p-4 rounded-xl border border-border/40 flex items-center gap-3">
                  <Cloud className="h-6 w-6 text-primary" />
                  <div>
                    <p className="text-xs text-muted-foreground font-medium">Conditions</p>
                    <p className="text-base font-semibold text-foreground">
                      {weatherInfo?.label || `Code ${weather.weathercode}`}
                    </p>
                  </div>
                </div>
              </div>

              {/* 7-Day Forecast Strip */}
              {dailyForecast && Array.isArray(dailyForecast.time) && dailyForecast.time.length > 0 && (
                <div className="pt-3 border-t border-border/40 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-foreground">7-Day Meteorological Outlook</span>
                    <span className="text-[10px] text-muted-foreground italic">Open-Meteo Meteorological Service</span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">
                    {dailyForecast.time.slice(0, 7).map((dateStr: string, idx: number) => {
                      const code = dailyForecast.weathercode?.[idx];
                      const maxT = Math.round(Number(dailyForecast.temperature_2m_max?.[idx] ?? 0));
                      const minT = Math.round(Number(dailyForecast.temperature_2m_min?.[idx] ?? 0));
                      const icon = WEATHER_CODE_MAP[code]?.icon || "🌤️";
                      const dayName = new Date(dateStr).toLocaleDateString("en-US", { weekday: "short" });
                      return (
                        <div
                          key={dateStr}
                          className="p-2.5 rounded-xl bg-muted/30 border border-border/40 text-center space-y-1"
                        >
                          <span className="text-[11px] font-semibold text-muted-foreground block">{dayName}</span>
                          <span className="text-xl block my-0.5">{icon}</span>
                          <div className="text-[11px] font-medium text-foreground">
                            <span className="font-bold">{maxT}°</span> / <span className="text-muted-foreground">{minT}°</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : weatherError ? (
            <div className="p-3 bg-destructive/10 text-destructive rounded-xl text-xs flex items-center justify-between">
              <span>{weatherError}</span>
              {destination.lat && destination.lon && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => fetchWeather(destination.lat, destination.lon)}
                  className="text-xs h-7 px-2"
                >
                  <RefreshCcw className="h-3 w-3 mr-1" /> Retry
                </Button>
              )}
            </div>
          ) : (
            <div className="p-3 bg-amber-500/10 border border-amber-500/20 text-amber-800 dark:text-amber-300 rounded-xl text-xs flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
              <span>
                Live weather requires coordinates for this location. Regional climate and seasonal recommendations are provided in the packing section below.
              </span>
            </div>
          )}
        </div>

        {/* Overview & Description with Translation */}
        <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60 space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2 border-b border-border/50 pb-3">
            <h2 className="text-xl font-bold text-foreground">Overview &amp; Description</h2>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground font-medium">Translate:</span>
              <LanguageSelector
                value={descLang}
                onChange={handleDescLangChange}
                className="text-xs py-1"
              />
            </div>
          </div>
          <p className="text-sm text-foreground/90 leading-relaxed pt-1">
            {isTranslatingDesc
              ? "Translating description..."
              : translatedDesc ||
                destination.description ||
                `Discover ${destination.name}, a captivating destination in ${locationLabel} offering rich cultural heritage, scenic landmarks, and memorable experiences for travelers.`}
          </p>

          {destination.tags && (
            <div className="flex items-center gap-1.5 flex-wrap pt-2">
              <span className="text-xs text-muted-foreground font-medium">Tags:</span>
              {destination.tags.split(",").map((t: string, idx: number) => (
                <Badge key={idx} variant="outline" className="text-[11px] py-0 px-2 font-normal">
                  {t.trim()}
                </Badge>
              ))}
            </div>
          )}
        </div>

        {/* Major Attractions & Places to Visit */}
        {attractions.length > 0 && (
          <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60 space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
                  <Ticket className="h-5 w-5 text-primary" />
                  <span>Major Attractions &amp; Places to Visit</span>
                </h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Must-visit sights and tourist points in {destination.name} ({attractions.length} places)
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {attractions.map((att: any) => {
                const attImg = resolveImageUrl(att.image) || activeImage;
                return (
                  <div
                    key={att.id || att.name}
                    className="group rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/40 transition-all overflow-hidden flex flex-col justify-between"
                  >
                    <div>
                      {att.image && (
                        <div className="relative h-32 w-full overflow-hidden bg-muted">
                          <img
                            src={attImg}
                            alt={att.name}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                            onError={(e) => {
                              (e.target as HTMLImageElement).style.display = "none";
                            }}
                          />
                        </div>
                      )}

                      <div className="p-3.5 space-y-1.5">
                        <div className="flex items-start justify-between gap-2">
                          <h4 className="font-bold text-sm text-foreground group-hover:text-primary transition-colors">
                            {att.name}
                          </h4>
                          {att.rating && (
                            <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-amber-500 shrink-0">
                              <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                              {Number(att.rating).toFixed(1)}
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-1.5 flex-wrap text-xs text-muted-foreground">
                          {att.category && (
                            <Badge variant="outline" className="text-[10px] py-0 px-1.5 h-4">
                              {att.category}
                            </Badge>
                          )}
                          <span className="text-[11px] font-medium">
                            {att.entry_fee > 0 ? `Entry: ₹${att.entry_fee}` : "Free Entry"}
                          </span>
                          {att.rating && (
                            <Badge
                              variant="secondary"
                              className="text-[10px] py-0 px-1.5 h-4 font-medium text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800"
                            >
                              {Number(att.rating) >= 4.5
                                ? "Top Rated"
                                : Number(att.rating) >= 4.0
                                ? "Highly Rated"
                                : "Visitor Rated"}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="p-3.5 pt-0">
                      <a
                        href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
                          att.name + ", " + destination.name
                        )}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline font-medium"
                      >
                        <ExternalLink className="h-3 w-3" /> Map &amp; Directions
                      </a>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Activities and Experiences */}
        {activities.length > 0 && (
          <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60 space-y-4">
            <div>
              <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
                <Activity className="h-5 w-5 text-coral" />
                <span>Activities &amp; Experiences</span>
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Popular things to do and curated outdoor experiences in {destination.name}
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3.5">
              {activities.map((act: any) => {
                const isSelected = selectedActivities.some(
                  (sa) => (sa.id && sa.id === act.id) || sa.name === act.name
                );

                return (
                  <div
                    key={act.id || act.name}
                    className={`p-4 rounded-xl border transition-all space-y-2.5 flex flex-col justify-between ${
                      isSelected
                        ? "bg-coral/5 border-coral/50 shadow-xs ring-1 ring-coral/20"
                        : "bg-muted/20 border-border/60 hover:border-coral/40"
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-sm text-foreground">{act.name}</span>
                        {act.price > 0 ? (
                          <span className="text-xs font-bold text-foreground">₹{act.price}</span>
                        ) : (
                          <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
                            Free
                          </span>
                        )}
                      </div>

                      {act.category && (
                        <p className="text-xs text-muted-foreground">{act.category}</p>
                      )}
                    </div>

                    <div className="pt-2 border-t border-border/40 flex items-center justify-between text-[11px] text-muted-foreground gap-2">
                      <div className="flex items-center gap-2">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3.5 w-3.5" /> {act.duration}h
                        </span>
                        {act.best_season && (
                          <span className="flex items-center gap-1 truncate max-w-[120px]">
                            <Calendar className="h-3.5 w-3.5 text-primary" /> {act.best_season}
                          </span>
                        )}
                      </div>

                      <Button
                        type="button"
                        size="sm"
                        variant={isSelected ? "default" : "outline"}
                        onClick={() => toggleActivitySelection(act)}
                        className={`text-[11px] h-7 px-2 font-medium shrink-0 ${
                          isSelected ? "bg-coral hover:bg-coral/90 text-white" : ""
                        }`}
                      >
                        {isSelected ? (
                          <>
                            <Check className="h-3 w-3 mr-1" /> Selected
                          </>
                        ) : (
                          <>
                            <Plus className="h-3 w-3 mr-1" /> Add to Trip
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Popular Restaurants & Dining (Phase 3) */}
        {restaurants.length > 0 && (
          <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60 space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
                  <Utensils className="h-5 w-5 text-amber-500" />
                  <span>Popular Restaurants &amp; Dining</span>
                </h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Dining options and available visitor ratings in {destination.name} ({restaurants.length} places)
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {restaurants.slice(0, 9).map((rst: any) => (
                <div
                  key={rst.id || rst.name}
                  className="p-4 rounded-xl border border-border/60 bg-muted/20 hover:border-amber-500/40 transition-colors space-y-3 flex flex-col justify-between"
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="font-bold text-sm text-foreground">
                        {rst.name}
                      </h4>
                      {rst.rating && (
                        <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-amber-500 shrink-0">
                          <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                          {Number(rst.rating).toFixed(1)}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-1.5 flex-wrap text-xs text-muted-foreground">
                      {rst.cuisine && (
                        <Badge variant="outline" className="text-[10px] py-0 px-1.5 h-4">
                          {rst.cuisine}
                        </Badge>
                      )}
                      {rst.price_range && (
                        <span className="text-[11px] font-medium text-foreground/80">
                          ₹{rst.price_range} for two
                        </span>
                      )}
                      {rst.rating && (
                        <Badge
                          variant="secondary"
                          className="text-[10px] py-0 px-1.5 h-4 font-medium text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800"
                        >
                          {Number(rst.rating) >= 4.0 ? "Recommended" : "Popular Choice"}
                        </Badge>
                      )}
                    </div>

                    {rst.address && (
                      <p className="text-[11px] text-muted-foreground line-clamp-2">
                        📍 {rst.address}
                      </p>
                    )}
                  </div>

                  <div className="pt-2 border-t border-border/40 flex items-center justify-between text-[11px]">
                    <span className="text-muted-foreground text-[10px]">
                      Available diner rating
                    </span>
                    <a
                      href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
                        rst.name + ", " + (rst.city || destination.name)
                      )}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:underline font-medium"
                    >
                      <ExternalLink className="h-3 w-3" /> Map &amp; Directions
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Destination Guest Reviews & Sentiment Insights (Phase 3) */}
        {destination.id && (
          <ReviewsSection
            entityType="destination"
            entityId={Number(destination.id)}
            title={`Guest Reviews & Sentiment Insights for ${destination.name}`}
          />
        )}

        {/* Smart Packing List Box */}
        <PackingListBox
          destination={destination}
          weather={weather}
          selectedActivities={selectedActivities}
          initialPackingList={packingState.packingList}
          initialPackedItems={packingState.packedItems}
          initialCustomItems={packingState.customItems}
          onStateChange={(st) => setPackingState(st)}
        />

        {/* Smart Day-by-Day Itinerary Box */}
        <SmartItineraryBox
          destination={destination}
          initialPlan={itineraryPlan}
          initialDays={itineraryDays}
          onPlanChange={(plan, days) => {
            setItineraryPlan(plan);
            setItineraryDays(days);
          }}
        />

        {/* Interactive Route Map & Optimizer */}
        <RouteOptimizerBox
          destination={destination}
          attractions={attractions}
          points={
            routeStops.length > 0
              ? routeStops
              : [
                  {
                    name: destination.name,
                    lat: destination.lat,
                    lon: destination.lon,
                  },
                  ...attractions.slice(0, 4).map((a: any) => ({
                    name: a.name,
                    lat: a.lat,
                    lon: a.lon,
                    category: a.category,
                    rating: a.rating,
                  })),
                ]
          }
          destinationName={destination.name}
          onRouteStopsChange={(stops) => setRouteStops(stops)}
        />

        {/* Save Customized Trip & Notes Card */}
        <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60 space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
                <Bookmark className="h-5 w-5 text-primary" />
                <span>Save Your Customized Trip</span>
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Preserve your itinerary, selected activities, optimized route stops, and packing checklist.
              </p>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              {isSaved && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate("/saved-trips")}
                  className="text-xs font-semibold px-3 h-9 shadow-sm border-primary/40 text-primary hover:bg-primary/10 flex items-center gap-1.5"
                >
                  <BookmarkCheck className="h-3.5 w-3.5" />
                  View in Saved Trips
                </Button>
              )}

              <Button
                onClick={handleSaveTrip}
                disabled={isSaving}
                size="sm"
                className={`text-xs font-semibold px-4 h-9 shadow-sm flex items-center gap-1.5 ${
                  isSaved ? "bg-emerald-600 hover:bg-emerald-700 text-white" : ""
                }`}
              >
              {isSaving ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                  Saving...
                </>
              ) : isSaved ? (
                <>
                  <Check className="h-3.5 w-3.5 text-white mr-1" />
                  Trip Saved ✓ (Click to Update)
                </>
              ) : (
                <>
                  <Bookmark className="h-3.5 w-3.5 mr-1" />
                  Save Customized Trip
                </>
              )}
            </Button>
            </div>
          </div>

          {saveStatusMsg && (
            <div className="flex items-center justify-between p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-800 dark:text-emerald-300">
              <span className="font-medium">{saveStatusMsg}</span>
              <Link
                to="/saved-trips"
                className="font-semibold underline hover:text-emerald-900 dark:hover:text-emerald-100 flex items-center gap-1 shrink-0 ml-2"
              >
                View in Saved Trips →
              </Link>
            </div>
          )}

          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">
              Personal Trip Notes &amp; Reminders (Optional)
            </label>
            <textarea
              value={userNotes}
              onChange={(e) => setUserNotes(e.target.value)}
              placeholder="e.g., booked beachfront cottage, remember scuba certification card, sunset photography spots..."
              className="w-full text-xs p-3 rounded-xl border border-border/60 bg-muted/20 focus:outline-none focus:ring-1 focus:ring-primary/40 min-h-[72px]"
            />
          </div>
        </div>

        {/* Booking Shortcuts */}
        <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60 space-y-4">
          <h2 className="text-xl font-bold text-foreground">Booking &amp; Travel Links</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <button
              onClick={() =>
                window.open(
                  `https://www.booking.com/searchresults.html?ss=${encodeURIComponent(destination.name)}`,
                  "_blank"
                )
              }
              className="bg-blue-600 hover:bg-blue-700 text-white py-2.5 px-3 rounded-xl shadow-sm text-xs font-medium transition"
            >
              🏨 Search Hotels
            </button>

            <button
              onClick={() =>
                window.open(
                  `https://www.skyscanner.net/transport/flights-to/${encodeURIComponent(destination.name)}`,
                  "_blank"
                )
              }
              className="bg-emerald-600 hover:bg-emerald-700 text-white py-2.5 px-3 rounded-xl shadow-sm text-xs font-medium transition"
            >
              ✈️ Search Flights
            </button>

            <button
              onClick={() =>
                window.open(
                  `https://www.google.com/maps/search/${encodeURIComponent(destination.name)}+tourist+attractions`,
                  "_blank"
                )
              }
              className="bg-slate-700 hover:bg-slate-800 text-white py-2.5 px-3 rounded-xl shadow-sm text-xs font-medium transition"
            >
              📍 Key Attractions
            </button>

            <button
              onClick={() =>
                window.open(
                  `https://www.makemytrip.com/holidays-india/${encodeURIComponent(destination.name)}-tour-packages.html`,
                  "_blank"
                )
              }
              className="bg-rose-600 hover:bg-rose-700 text-white py-2.5 px-3 rounded-xl shadow-sm text-xs font-medium transition"
            >
              🧳 Explore Packages
            </button>
          </div>
        </div>

        {/* Call to Action: Plan a Trip with AI */}
        <div className="rounded-2xl p-6 sm:p-8 bg-gradient-to-r from-primary/10 via-primary/5 to-coral/10 border border-primary/20 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="space-y-1 text-center sm:text-left">
            <h3 className="text-xl font-bold text-foreground flex items-center justify-center sm:justify-start gap-2">
              <Sparkles className="h-5 w-5 text-coral" />
              <span>Ready to visit {destination.name}?</span>
            </h3>
            <p className="text-xs sm:text-sm text-muted-foreground max-w-lg">
              Let TravelMate's AI assistant craft a customized, day-by-day plan with attractions, hotels, and packing essentials tailored to your dates and budget.
            </p>
          </div>

          <div className="flex items-center gap-2.5 shrink-0 flex-wrap justify-center">
            <Button
              size="sm"
              onClick={handlePlanTrip}
              className="text-xs h-9 px-4 flex items-center gap-1.5 font-medium shadow-sm"
            >
              <Compass className="h-4 w-4" />
              <span>Start Trip Planning</span>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DestinationPage;