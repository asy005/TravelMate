import { useState } from "react";
import { Loader2, ImagePlus, Landmark, Navigation } from "lucide-react";

export const LandmarkDetector = () => {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    setFile(selected);
    setPreview(URL.createObjectURL(selected));
    setResult(null);
  };

  const uploadForDetection = async () => {
    if (!file) return;

    setLoading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://127.0.0.1:8000/image/landmark", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      setResult(data);
    } catch (error) {
      console.error("Detection failed:", error);
    }

    setLoading(false);
  };

  const saveAndNavigate = () => {
    if (!result) return;

    // Save to local storage
    const newDest = {
      id: Date.now(),
      name: result.landmark,
      country: "Unknown",
      description: `You uploaded a photo and AI detected it as ${result.landmark}.`,
      image: preview,
      lat: null,
      lon: null,
      mood: "Unknown",
      budget: "Unknown",
      best_time: "Unknown",
    };

    const saved = localStorage.getItem("travelmate_recommendations");
    let arr = [];

    if (saved) {
      try {
        arr = JSON.parse(saved).destinations || [];
      } catch {
        arr = [];
      }
    }

    arr.push(newDest);

    localStorage.setItem(
      "travelmate_recommendations",
      JSON.stringify({ destinations: arr })
    );

    // Redirect to the destination page
    window.location.href = `/destination/${newDest.id}`;
  };

  return (
    <div className="bg-white/10 backdrop-blur-xl p-8 rounded-2xl shadow-lg border border-white/20 max-w-xl mx-auto">

      <h2 className="text-3xl font-bold mb-6 flex items-center gap-2">
        <ImagePlus className="w-7 h-7 text-primary" />
        Landmark Detection
      </h2>

      {/* Upload Box */}
      <label className="flex flex-col items-center justify-center w-full h-52 border-2 border-dashed border-white/40 rounded-xl cursor-pointer hover:bg-white/5 transition">
        <span className="text-lg text-white/80">Click to upload photo</span>
        <input type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
      </label>

      {/* Preview */}
      {preview && (
        <div className="mt-6">
          <p className="text-white/70 mb-2">Image Preview:</p>
          <img src={preview} className="w-full h-56 object-cover rounded-xl shadow-lg" />
        </div>
      )}

      {/* Detect Button */}
      {file && !result && (
        <button
          onClick={uploadForDetection}
          disabled={loading}
          className="w-full mt-6 bg-primary text-white py-3 rounded-xl hover:opacity-90 transition flex justify-center"
        >
          {loading ? (
            <Loader2 className="h-6 w-6 animate-spin" />
          ) : (
            "Detect Landmark"
          )}
        </button>
      )}

      {/* Result Box */}
      {result && (
        <div className="mt-8 bg-card/60 rounded-xl p-6 border border-white/20 shadow-xl">
          <h3 className="text-2xl font-semibold flex items-center gap-2 mb-3">
            <Landmark className="text-yellow-300" />
            Detected Landmark
          </h3>

          <p className="text-xl mb-2">
            <b>{result.landmark}</b>
          </p>

          <p className="text-white/70">
            Confidence: {(result.confidence * 100).toFixed(2)}%
          </p>

          <button
            onClick={saveAndNavigate}
            className="w-full mt-6 bg-green-600 text-white py-3 rounded-xl hover:bg-green-700 flex items-center justify-center gap-2"
          >
            <Navigation className="w-5 h-5" />
            Plan a Trip to This Place
          </button>
        </div>
      )}
    </div>
  );
};
