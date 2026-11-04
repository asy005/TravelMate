import { useEffect, useState } from "react";
import axios from "axios";
import { useParams, useNavigate } from "react-router-dom";
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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

import { HighlightsBox } from "@/components/HighlightsBox";
import { PackingListBox } from "@/components/PackingListBox";
import { RouteOptimizerBox } from "@/components/RouteOptimizerBox";
import { SmartItineraryBox } from "@/components/SmartItineraryBox";
import { LanguageSelector, getStoredLanguage } from "@/components/LanguageSelector";
import { translateText, getDestinationById, resolveImageUrl } from "@/lib/api";
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
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [weatherError, setWeatherError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [descLang, setDescLang] = useState<string>(getStoredLanguage());
  const [translatedDesc, setTranslatedDesc] = useState<string | null>(null);
  const [isTranslatingDesc, setIsTranslatingDesc] = useState(false);
  const [activeImage, setActiveImage] = useState<string>(DEFAULT_IMAGE);

  const fetchWeather = async (lat: number, lon: number) => {
    setWeatherLoading(true);
    setWeatherError(null);
    try {
      const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true`;
      const res = await axios.get(url, { timeout: 8000 });
      setWeather(res.data?.current_weather || null);
    } catch (err: any) {
      console.warn("Weather fetch failed:", err);
      setWeatherError("Weather service temporarily unreachable. Click retry to update.");
      setWeather(null);
    } finally {
      setWeatherLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    const loadData = async () => {
      let foundDest: any = null;

      // 1. Check Landmark Recognition History (localStorage)
      try {
        const landmarkSaved = localStorage.getItem("travelmate_landmark_history");
        if (landmarkSaved) {
          const landmarkList = JSON.parse(landmarkSaved);
          foundDest = landmarkList.find(
            (d: any) => String(d.id) === id || (d.name && String(d.name) === id)
          );
        }
      } catch {}

      // 2. Check Curated Local Dataset (matches DB IDs)
      if (!foundDest) {
        foundDest = DESTINATIONS.find(
          (d) => String(d.id) === id || d.name.toLowerCase() === id?.toLowerCase()
        );
      }

      // 3. Check AI Recommendations (localStorage)
      if (!foundDest) {
        try {
          const recSaved = localStorage.getItem("travelmate_recommendations");
          if (recSaved) {
            const parsed = JSON.parse(recSaved);
            foundDest = (parsed.destinations || []).find((d: any) => String(d.id) === id);
          }
        } catch {}
      }

      // 4. Fetch from Backend API: /destinations/:id (Always attempt backend for full attractions/activities)
      try {
        if (id) {
          const apiData = await getDestinationById(id);
          if (apiData && isMounted) {
            foundDest = { ...foundDest, ...apiData };
          }
        }
      } catch {
        // Use local fallback if backend request failed
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
      // Fallback to original
    } finally {
      setIsTranslatingDesc(false);
    }
  };

  const handlePlanTrip = () => {
    navigate(`/?destination=${encodeURIComponent(destination?.name || "")}#trip-chat-input`);
    setTimeout(() => {
      const inputEl = document.getElementById("trip-chat-input");
      if (inputEl) {
        inputEl.scrollIntoView({ behavior: "smooth", block: "center" });
        inputEl.focus();
      }
    }, 150);
  };

  const handleOpenAIChat = () => {
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
            <Button
              variant="outline"
              size="sm"
              onClick={handleOpenAIChat}
              className="text-xs h-8 flex items-center gap-1.5"
            >
              <MessageCircle className="h-3.5 w-3.5 text-primary" />
              <span className="hidden sm:inline">AI Chat</span>
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
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1">
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
            <p className="text-xs text-muted-foreground italic">
              Live weather requires coordinates for this location.
            </p>
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

                        <div className="flex items-center gap-2 flex-wrap text-xs text-muted-foreground">
                          {att.category && (
                            <Badge variant="outline" className="text-[10px] py-0 px-1.5 h-4">
                              {att.category}
                            </Badge>
                          )}
                          <span className="text-[11px] font-medium">
                            {att.entry_fee > 0 ? `Entry: ₹${att.entry_fee}` : "Free Entry"}
                          </span>
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
              {activities.map((act: any) => (
                <div
                  key={act.id || act.name}
                  className="p-4 rounded-xl border border-border/60 bg-muted/20 hover:border-coral/40 transition-colors space-y-2 flex flex-col justify-between"
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

                  <div className="pt-2 border-t border-border/40 flex items-center justify-between text-[11px] text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" /> {act.duration}h
                    </span>
                    {act.best_season && (
                      <span className="flex items-center gap-1 truncate max-w-[140px]">
                        <Calendar className="h-3 w-3 text-primary" /> {act.best_season}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* AI Highlights Box */}
        <HighlightsBox destination={destination} />

        {/* AI Packing List Box */}
        <PackingListBox destination={destination} weather={weather} />

        {/* AI Smart Itinerary Box */}
        <SmartItineraryBox destination={destination} />

        {/* AI Route Optimizer Box */}
        <RouteOptimizerBox
          points={[
            {
              name: destination.name,
              lat: destination.lat,
              lon: destination.lon,
            },
            ...(attractions.slice(0, 4).map((a: any) => ({
              name: a.name,
              lat: a.lat,
              lon: a.lon,
            }))),
          ]}
          destinationName={destination.name}
        />

        {/* Route Map & Navigation */}
        <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60 space-y-4">
          <h2 className="text-xl font-bold text-foreground">Route Map &amp; Navigation</h2>

          <div className="w-full rounded-xl border border-dashed border-border bg-muted/20 flex flex-col items-center justify-center gap-3 p-8 text-center">
            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
              <Compass className="h-5 w-5" />
            </div>
            <div>
              <p className="font-semibold text-base text-foreground mb-1">
                Directions for {destination.name}
              </p>
              <p className="text-xs text-muted-foreground max-w-md">
                Direct external navigation is active. Use the links below to view live terrain, traffic, and step-by-step turn directions.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 justify-center mt-2">
              <a
                href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
                  destination.name + (destination.country ? ", " + destination.country : "")
                )}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 bg-primary text-primary-foreground px-4 py-2 rounded-xl text-xs font-semibold shadow-sm hover:opacity-90 transition"
              >
                <ExternalLink className="h-3.5 w-3.5" /> View on Google Maps
              </a>
              <a
                href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(
                  destination.name + (destination.country ? ", " + destination.country : "")
                )}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 bg-green-600 text-white px-4 py-2 rounded-xl text-xs font-semibold shadow-sm hover:opacity-90 transition"
              >
                <ExternalLink className="h-3.5 w-3.5" /> Get Directions
              </a>
            </div>
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
              variant="outline"
              size="sm"
              onClick={handleOpenAIChat}
              className="text-xs h-9 px-3.5 flex items-center gap-1.5"
            >
              <MessageCircle className="h-4 w-4 text-primary" />
              <span>Open in AI Chat</span>
            </Button>
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
