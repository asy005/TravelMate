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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

import { HighlightsBox } from "@/components/HighlightsBox";
import { PackingListBox } from "@/components/PackingListBox";
import { RouteOptimizerBox } from "@/components/RouteOptimizerBox";
import { SmartItineraryBox } from "@/components/SmartItineraryBox";
import { LanguageSelector, getStoredLanguage } from "@/components/LanguageSelector";
import { translateText } from "@/lib/api";
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

    if (foundDest) {
      setDestination(foundDest);
      setLoading(false);
      if (foundDest.lat && foundDest.lon) {
        fetchWeather(foundDest.lat, foundDest.lon);
      }
    } else {
      // 4. Fetch from Backend API: /destinations/:id
      fetch(`http://127.0.0.1:8000/destinations/${id}`)
        .then((res) => {
          if (!res.ok) throw new Error("Destination not found");
          return res.json();
        })
        .then((data) => {
          setDestination(data);
          if (data.lat && data.lon) {
            fetchWeather(data.lat, data.lon);
          }
        })
        .catch(() => {
          setDestination(null);
        })
        .finally(() => {
          setLoading(false);
        });
    }
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
      // Fallback
    } finally {
      setIsTranslatingDesc(false);
    }
  };

  const handlePlanTrip = () => {
    navigate(`/?destination=${encodeURIComponent(destination?.name || "")}#trip-chat-input`);
    const inputEl = document.getElementById("trip-chat-input");
    if (inputEl) {
      inputEl.scrollIntoView({ behavior: "smooth", block: "center" });
      inputEl.focus();
    }
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
          <ArrowLeft className="h-4 w-4" /> Back to Home
        </Button>
      </div>
    );
  }

  const weatherInfo = weather ? WEATHER_CODE_MAP[weather.weathercode] : null;

  return (
    <div className="min-h-screen bg-background">
      {/* Top Navigation Bar */}
      <div className="sticky top-0 z-40 bg-background/80 backdrop-blur-md border-b border-border/50 px-6 py-3">
        <div className="container mx-auto flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(-1)}
            className="text-xs h-8 flex items-center gap-1.5"
          >
            <ArrowLeft className="h-4 w-4" /> Back
          </Button>
          <Button
            size="sm"
            onClick={handlePlanTrip}
            className="text-xs h-8 flex items-center gap-1.5"
          >
            <Compass className="h-3.5 w-3.5" /> Plan Trip Here
          </Button>
        </div>
      </div>

      <div className="container mx-auto px-6 py-8 max-w-5xl space-y-8 animate-fade-up">
        {/* Title Header */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
              {destination.name}
            </h1>
            {destination.type && (
              <Badge variant="outline" className="text-xs">
                {destination.type}
              </Badge>
            )}
            {destination.mood && (
              <Badge variant="secondary" className="text-xs">
                {destination.mood}
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground flex items-center gap-1.5 font-medium">
            <MapPin className="h-4 w-4 text-coral shrink-0" />
            {[destination.city || destination.state, destination.country || "India"]
              .filter(Boolean)
              .join(", ")}
          </p>
        </div>

        {/* Hero Image */}
        <div className="w-full h-72 sm:h-96 rounded-2xl overflow-hidden shadow-md border border-border/50 relative bg-muted">
          <img
            src={
              destination.image ||
              destination.thumbnail_url ||
              "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&q=80&w=1200"
            }
            alt={destination.name}
            className="w-full h-full object-cover"
          />
        </div>

        {/* Weather Card */}
        <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60">
          <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
            <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
              <Sun className="h-5 w-5 text-amber-500" />
              <span>Current Weather</span>
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

        {/* About this Destination */}
        <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60 space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2 border-b border-border/50 pb-3">
            <h2 className="text-xl font-bold text-foreground">About this Destination</h2>
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
                "A captivating destination offering rich culture, memorable sightseeing, and delightful local experiences."}
          </p>
        </div>

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
          ]}
          destinationName={destination.name}
        />

        {/* Route Map & Navigation */}
        <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60 space-y-4">
          <h2 className="text-xl font-bold text-foreground">Route Map &amp; Navigation</h2>

          {/* Clean fallback panel with actionable Google Maps directions */}
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
      </div>
    </div>
  );
};

export default DestinationPage;
