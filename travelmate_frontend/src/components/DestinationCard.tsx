import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useState } from "react";

export const DestinationCard = ({ destination, onPlanTrip }: any) => {
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);

  async function saveFavorite(e: React.MouseEvent) {
    e.stopPropagation(); // prevent navigating
    setSaving(true);

    try {
      const token = localStorage.getItem("travelmate_token");
      if (!token) {
        alert("Please login to save favorites.");
        setSaving(false);
        return;
      }

      // Check if already saved in localStorage
      const savedFavorites = JSON.parse(localStorage.getItem("travelmate_favorites") || "[]");
      const alreadySaved = savedFavorites.some(
        (fav: any) => fav.destination_name === destination.name
      );

      if (alreadySaved) {
        alert("Already saved in favorites.");
        setSaving(false);
        return;
      }

      const payload = {
        destination_name: destination.name,
        destination_payload: destination,
      };

      const params = new URLSearchParams({ destination_id: String(destination.id) });

      const res = await fetch(`http://127.0.0.1:8000/favorites/add?${params.toString()}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      const json = await res.json();

      if (!res.ok) {
        console.error("Save error response:", json);
        const message =
          typeof json === "object"
            ? json.detail || json.error || JSON.stringify(json)
            : json || "Failed to save favorite";

            alert(typeof message === "string" ? message : JSON.stringify(message, null, 2));

      } else {
        // Save locally as well
        const updatedFavorites = [...savedFavorites, payload];
        localStorage.setItem("travelmate_favorites", JSON.stringify(updatedFavorites));
        alert("Saved to favorites ✅");
      }
    } catch (err) {
      console.error(err);
      alert("Network error saving favorite");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="group cursor-pointer bg-card/60 backdrop-blur-md rounded-2xl shadow-lg border border-white/10 overflow-hidden transition transform hover:scale-[1.02]"
      onClick={() => navigate(`/destination/${destination.id}`)}
    >
      <div className="p-5 text-dark-blue">
        {/* Header */}
        <h3 className="text-xl font-semibold mb-1">{destination.name}</h3>
  
        {/* Description */}
        <p className="text-sm mb-4">{destination.description}</p>
  
        {/* Action Buttons */}
        <div className="flex justify-between items-center">
          <Button
            variant="secondary"
            onClick={(e) => {
              e.stopPropagation();
              onPlanTrip(destination);
            }}
          >
            Plan Trip
          </Button>
  
          <button
            onClick={saveFavorite}
            className="bg-yellow-500 text-sm px-3 py-1 rounded ml-3"
            disabled={saving}
            title="Save to favorites"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );  
};
