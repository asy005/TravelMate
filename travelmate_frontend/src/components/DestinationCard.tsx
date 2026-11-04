import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Star, MapPin, Heart, Compass, ArrowRight } from "lucide-react";
import { addFavorite } from "@/lib/api";

export const DestinationCard = ({ destination, onPlanTrip }: any) => {
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);

  const checkIsSaved = useCallback(() => {
    try {
      const savedFavorites = JSON.parse(localStorage.getItem("travelmate_favorites") || "[]");
      return savedFavorites.some(
        (fav: any) => fav.destination_name === destination.name || fav.name === destination.name
      );
    } catch {
      return false;
    }
  }, [destination.name]);

  const [isSaved, setIsSaved] = useState(() => checkIsSaved());

  // Keep heart in sync when the Favorites page removes an item
  useEffect(() => {
    const handler = () => setIsSaved(checkIsSaved());
    window.addEventListener("travelmate_favorites_changed", handler);
    return () => window.removeEventListener("travelmate_favorites_changed", handler);
  }, [checkIsSaved]);
  const [imgSrc, setImgSrc] = useState(
    destination.image ||
      destination.thumbnail_url ||
      "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&q=80&w=800"
  );

  const locationDisplay = [
    destination.state || destination.region,
    destination.country || "India",
  ]
    .filter(Boolean)
    .join(", ");

  const handleCardClick = () => {
    navigate(`/destination/${destination.id}`);
  };

  const handleToggleFavorite = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setSaving(true);

    try {
      const savedFavorites = JSON.parse(localStorage.getItem("travelmate_favorites") || "[]");
      const existsIndex = savedFavorites.findIndex(
        (fav: any) => fav.destination_name === destination.name || fav.name === destination.name
      );

      if (existsIndex >= 0) {
        // Remove from favorites
        savedFavorites.splice(existsIndex, 1);
        localStorage.setItem("travelmate_favorites", JSON.stringify(savedFavorites));
        setIsSaved(false);
      } else {
        // Add to favorites with timestamp
        const payload = {
          destination_name: destination.name,
          destination_payload: destination,
          saved_at: new Date().toISOString(),
        };
        savedFavorites.push(payload);
        localStorage.setItem("travelmate_favorites", JSON.stringify(savedFavorites));
        setIsSaved(true);

        const token = localStorage.getItem("travelmate_token");
        if (token) {
          addFavorite(destination.id, payload).catch(() => {
            // Local persistence succeeded
          });
        }
      }

      // Notify Favorites page and other card instances
      window.dispatchEvent(new CustomEvent("travelmate_favorites_changed"));
    } catch (err) {
      console.error("Favorite toggle error:", err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      onClick={handleCardClick}
      className="group cursor-pointer bg-card rounded-2xl overflow-hidden border border-border/60 hover:border-primary/40 shadow-sm hover:shadow-md transition-all duration-300 flex flex-col h-full"
    >
      {/* Destination Image with Badge Overlays */}
      <div className="relative h-48 w-full overflow-hidden bg-muted">
        <img
          src={imgSrc}
          alt={destination.name}
          onError={() => {
            setImgSrc(
              "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&q=80&w=800"
            );
          }}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
          loading="lazy"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-black/10" />

        {/* Favorite Button Overlay */}
        <button
          onClick={handleToggleFavorite}
          disabled={saving}
          title={isSaved ? "Remove from favorites" : "Save to favorites"}
          className="absolute top-3 right-3 h-8 w-8 rounded-full bg-background/80 backdrop-blur-md flex items-center justify-center hover:bg-background transition-colors text-foreground shadow-sm"
        >
          <Heart
            className={`h-4 w-4 ${
              isSaved ? "fill-red-500 text-red-500" : "text-muted-foreground hover:text-red-500"
            }`}
          />
        </button>

        {/* Badges on bottom of image */}
        <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between text-white text-xs">
          <div className="flex items-center gap-1.5 flex-wrap">
            {destination.type && (
              <span className="bg-black/60 backdrop-blur-sm px-2 py-0.5 rounded-md font-medium text-[11px] text-white">
                {destination.type}
              </span>
            )}
            {destination.mood && (
              <span className="bg-primary/80 backdrop-blur-sm px-2 py-0.5 rounded-md font-medium text-[11px] text-primary-foreground">
                {destination.mood}
              </span>
            )}
          </div>
          {destination.avg_rating && (
            <span className="bg-black/60 backdrop-blur-sm px-2 py-0.5 rounded-md flex items-center gap-1 font-semibold text-amber-300 text-[11px]">
              <Star className="h-3 w-3 fill-amber-300 text-amber-300" />
              {Number(destination.avg_rating).toFixed(1)}
            </span>
          )}
        </div>
      </div>

      {/* Card Content */}
      <div className="p-5 flex-1 flex flex-col justify-between space-y-3">
        <div>
          {/* Destination Name & Location */}
          <h3 className="text-lg font-bold text-foreground group-hover:text-primary transition-colors flex items-center justify-between">
            <span>{destination.name}</span>
          </h3>

          {locationDisplay && (
            <p className="text-xs text-muted-foreground flex items-center gap-1 mt-1 font-medium">
              <MapPin className="h-3 w-3 text-coral shrink-0" />
              <span>{locationDisplay}</span>
            </p>
          )}

          {/* Description */}
          <p className="text-xs text-muted-foreground leading-relaxed mt-2.5 line-clamp-2">
            {destination.description}
          </p>
        </div>

        {/* Footer Info & Actions */}
        <div className="pt-3 border-t border-border/50 flex items-center justify-between gap-2 mt-auto">
          {destination.budget && (
            <Badge variant="outline" className="text-[11px] font-normal capitalize">
              {destination.budget} budget
            </Badge>
          )}

          <div className="flex items-center gap-2 ml-auto">
            <Button
              variant="outline"
              size="sm"
              className="text-xs h-8 px-2.5"
              onClick={(e) => {
                e.stopPropagation();
                handleCardClick();
              }}
            >
              Details
            </Button>
            <Button
              variant="default"
              size="sm"
              className="text-xs h-8 px-3 flex items-center gap-1"
              onClick={(e) => {
                e.stopPropagation();
                if (onPlanTrip) onPlanTrip(destination);
                else navigate(`/?destination=${encodeURIComponent(destination.name)}#trip-chat-input`);
              }}
            >
              <Compass className="h-3 w-3" /> Plan Trip
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
