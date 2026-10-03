import { useEffect, useState } from "react";
import axios from "axios";
import { useParams } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { HighlightsBox } from "@/components/HighlightsBox";
import { PackingListBox } from "@/components/PackingListBox";
import { RouteOptimizerBox } from "@/components/RouteOptimizerBox";
import { SmartItineraryBox } from "@/components/SmartItineraryBox";

const DestinationPage = () => {
  const { id } = useParams();
  const [destination, setDestination] = useState<any>(null);
  const [weather, setWeather] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const saved = localStorage.getItem("travelmate_recommendations");
    if (!saved) return;

    const parsed = JSON.parse(saved);
    const dest = parsed.destinations.find((d: any) => String(d.id) === id);

    setDestination(dest);

    if (dest?.lat && dest?.lon) {
      fetchWeather(dest.lat, dest.lon);
    }

    setLoading(false);
  }, [id]);

  const fetchWeather = async (lat: number, lon: number) => {
    try {
      const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true`;
      const res = await axios.get(url);
      setWeather(res.data.current_weather);
    } catch (err) {
      console.log("Weather error:", err);
    }
  };

  if (loading || !destination) {
    return (
      <div className="h-screen flex items-center justify-center text-xl">
        <Loader2 className="h-6 w-6 animate-spin mr-2" />
        Loading destination...
      </div>
    );
  }

  return (
    <div className="container mx-auto px-6 py-12 space-y-16">

      {/* Title */}
      <div>
        <h1 className="text-4xl font-bold">{destination.name}</h1>
        <p className="text-muted-foreground">{destination.country}</p>
      </div>

      {/* Image */}
      <div className="w-full h-80 rounded-xl overflow-hidden mb-10 shadow-xl">
        <img
          src={destination.image || "https://via.placeholder.com/800x400"}
          className="w-full h-full object-cover"
        />
      </div>

      {/* Weather */}
      <div className="bg-card/70 backdrop-blur-xl shadow-xl p-6 rounded-2xl border border-white/10">
        <h2 className="text-2xl font-semibold mb-3">🌤 Current Weather</h2>
        {weather ? (
          <ul className="text-lg space-y-1">
            <li>Temperature: <b>{weather.temperature}°C</b></li>
            <li>Wind Speed: <b>{weather.windspeed} km/h</b></li>
            <li>Condition Code: <b>{weather.weathercode}</b></li>
          </ul>
        ) : (
          <p className="text-muted-foreground">Unable to load weather.</p>
        )}
      </div>

      {/* About */}
      <div className="bg-white/10 p-6 rounded-xl backdrop-blur-xl border border-white/20 shadow-lg">
        <h2 className="text-2xl font-semibold mb-4">About this Destination</h2>
        <p className="text-lg">{destination.description}</p>
      </div>

      {/* AI Highlights */}
      <HighlightsBox destination={destination} />

      {/* AI Packing List */}
      <PackingListBox
      destination={destination}
      weather={weather}
      />

      {/* AI Smart Itinerary */}
      <SmartItineraryBox destination={destination} />

      {/* AI Route Optimizer */}
      <RouteOptimizerBox
        points={[
        {
          name: destination.name,
          lat: destination.lat,
          lon: destination.lon,
    },
  ]}
/>

      {/* Google Maps View */}
      <div className="bg-white/10 p-6 rounded-xl backdrop-blur-xl border border-white/20 shadow-lg mt-12">
        <h2 className="text-2xl font-semibold mb-4">🗺️ Route Map</h2>

        <div className="w-full h-[400px] rounded-xl overflow-hidden shadow-lg border border-white/20">
          <iframe
            width="100%"
            height="100%"
            loading="lazy"
            allowFullScreen
            src={`https://www.google.com/maps/embed/v1/place?key=AIzaSyDUMMY-KEY&zoom=10&q=${encodeURIComponent(
              destination.name + ", " + destination.country
            )}`}
          ></iframe>
        </div>

        <a
          href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(
            destination.name
          )}`}
          target="_blank"
          className="mt-4 inline-block bg-primary text-white px-6 py-3 rounded-xl shadow-lg hover:opacity-90 transition"
        >
          👉 Open Navigation
        </a>
      </div>

      {/* Booking Shortcuts */}
      <div className="bg-white/10 p-6 rounded-xl backdrop-blur-xl border border-white/20 shadow-lg mb-16">
        <h2 className="text-2xl font-semibold mb-4">✈️ Bookings</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <button
            onClick={() =>
              window.open(
                `https://www.booking.com/searchresults.html?ss=${destination.name}`,
                "_blank"
              )
            }
            className="bg-blue-600 text-white py-3 px-4 rounded-xl shadow-md"
          >
            🏨 Hotels
          </button>

          <button
            onClick={() =>
              window.open(
                `https://www.skyscanner.net/transport/flights-to/${destination.name}`,
                "_blank"
              )
            }
            className="bg-green-600 text-white py-3 px-4 rounded-xl shadow-md"
          >
            ✈️ Flights
          </button>

          <button
            onClick={() =>
              window.open(
                `https://www.google.com/maps/search/${destination.name} tourist attractions`,
                "_blank"
              )
            }
            className="bg-gray-700 text-white py-3 px-4 rounded-xl shadow-md"
          >
            📍 Places
          </button>

          <button
            onClick={() =>
              window.open(
                `https://www.makemytrip.com`,
                "_blank"
              )
            }
            className="bg-red-600 text-white py-3 px-4 rounded-xl shadow-md"
          >
            🧳 Packages
          </button>
        </div>
      </div>

    </div>
  );
};

export default DestinationPage;