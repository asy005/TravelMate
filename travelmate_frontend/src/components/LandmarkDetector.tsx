import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  Loader2,
  Landmark,
  Compass,
  ArrowRight,
  Upload,
  X,
  History,
  Trash2,
  CheckCircle2,
  MapPin,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { predictLandmark } from "@/lib/api";

export interface LandmarkHistoryItem {
  id: number;
  name: string;
  city?: string;
  country?: string;
  confidence: number;
  image: string;
  timestamp: string;
  lat?: number | null;
  lon?: number | null;
  description?: string;
}

const STORAGE_KEY = "travelmate_landmark_history";

export const LandmarkDetector = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<LandmarkHistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  // Load persistent history on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        setHistory(JSON.parse(saved));
      }
    } catch {
      setHistory([]);
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    if (!selected.type.startsWith("image/")) {
      setError("Please select a valid image file (JPEG, PNG, WebP).");
      return;
    }

    setFile(selected);
    setPreview(URL.createObjectURL(selected));
    setResult(null);
    setError(null);
  };

  const handleClearSelected = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const uploadForDetection = async () => {
    if (!file) return;

    setLoading(true);
    setError(null);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const data = await predictLandmark(file);
      setResult(data);

      // Save to landmark recognition history (NEVER mix into travelmate_recommendations!)
      const historyItem: LandmarkHistoryItem = {
        id: Date.now(),
        name: data.landmark,
        city: data.city || "Unknown",
        country: data.country || "Unknown",
        confidence: data.confidence,
        image: preview || "",
        timestamp: new Date().toISOString(),
        lat: data.lat || null,
        lon: data.lon || null,
        description: data.description || `AI detected ${data.landmark}.`,
      };

      const updatedHistory = [historyItem, ...history.filter((h) => h.name !== data.landmark)].slice(0, 10);
      setHistory(updatedHistory);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updatedHistory));
      } catch {
        // Storage quota exceeded or disabled
      }
    } catch (err: any) {
      console.error("Detection failed:", err);
      setError(err?.message || "Failed to identify landmark. Please check backend connection and try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleNavigateToDestination = (landmarkData: any) => {
    const destId = landmarkData.id || Date.now();
    // Ensure this landmark is findable by DestinationPage in landmark history
    const existingHistory = [...history];
    if (!existingHistory.some((h) => h.id === destId)) {
      const item: LandmarkHistoryItem = {
        id: destId,
        name: landmarkData.landmark || landmarkData.name,
        city: landmarkData.city,
        country: landmarkData.country,
        confidence: landmarkData.confidence || 0.9,
        image: preview || landmarkData.image || "",
        timestamp: new Date().toISOString(),
        lat: landmarkData.lat,
        lon: landmarkData.lon,
        description: landmarkData.description,
      };
      existingHistory.unshift(item);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(existingHistory));
      } catch {}
    }

    navigate(`/destination/${destId}`);
  };

  const handlePlanTrip = (landmarkName: string) => {
    navigate(`/?destination=${encodeURIComponent(landmarkName)}#trip-chat-input`);
    const inputEl = document.getElementById("trip-chat-input");
    if (inputEl) {
      inputEl.scrollIntoView({ behavior: "smooth", block: "center" });
      inputEl.focus();
    }
  };

  const handleClearHistory = () => {
    setHistory([]);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {}
  };

  return (
    <div className="rounded-2xl border bg-white dark:bg-gray-900 shadow-sm overflow-hidden p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2 pb-4 border-b border-border/50">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
            <Landmark className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold tracking-tight text-foreground">
              Landmark Recognition
            </h2>
            <p className="text-xs text-muted-foreground">
              Upload a photo to detect world landmarks and explore destination guides.
            </p>
          </div>
        </div>

        {/* History Toggle Button */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowHistory(!showHistory)}
          className="text-xs h-8 flex items-center gap-1.5"
        >
          <History className="h-3.5 w-3.5" />
          <span>History ({history.length})</span>
          {showHistory ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </Button>
      </div>

      {/* Upload & Preview Zone (Fixed whitespace & responsive aspect ratio) */}
      {!preview ? (
        <label className="flex flex-col items-center justify-center w-full py-8 px-4 border-2 border-dashed border-border/70 hover:border-primary/50 rounded-xl cursor-pointer bg-muted/20 hover:bg-muted/40 transition-colors text-center group">
          <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center text-primary mb-3 group-hover:scale-105 transition-transform">
            <Upload className="h-5 w-5" />
          </div>
          <span className="text-sm font-semibold text-foreground">
            Click to upload a monument or landmark photo
          </span>
          <span className="text-xs text-muted-foreground mt-1">
            Supports JPEG, PNG, WebP up to 10 MB
          </span>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            className="hidden"
          />
        </label>
      ) : (
        /* Image Preview Container (object-contain, max-h-64, no excessive whitespace) */
        <div className="space-y-4">
          <div className="relative rounded-xl border border-border/60 bg-muted/30 p-2 overflow-hidden flex items-center justify-center">
            <img
              src={preview}
              alt="Uploaded landmark preview"
              className="max-h-60 max-w-full object-contain rounded-lg shadow-sm mx-auto"
            />
            <button
              onClick={handleClearSelected}
              className="absolute top-4 right-4 h-7 w-7 rounded-full bg-background/80 hover:bg-background backdrop-blur-sm flex items-center justify-center text-muted-foreground hover:text-foreground shadow-sm transition-colors"
              title="Remove image"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
            <span className="truncate max-w-xs">{file?.name}</span>
            <button
              onClick={handleClearSelected}
              className="text-red-500 hover:underline"
            >
              Change image
            </button>
          </div>

          {!result && (
            <Button
              onClick={uploadForDetection}
              disabled={loading}
              className="w-full h-11 text-sm font-medium flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Identifying landmark...
                </>
              ) : (
                <>
                  <Landmark className="h-4 w-4" />
                  Detect Landmark
                </>
              )}
            </Button>
          )}
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50/50 dark:bg-red-950/20 p-3 text-xs text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Result Card */}
      {result && (
        <div className="bg-card rounded-xl p-5 border border-primary/20 bg-primary/5 space-y-4 animate-fade-up">
          <div className="flex items-start justify-between flex-wrap gap-2">
            <div>
              <p className="text-xs uppercase tracking-wide text-primary font-semibold flex items-center gap-1">
                <CheckCircle2 className="h-3.5 w-3.5" /> Landmark Identified
              </p>
              <h3 className="text-2xl font-bold text-foreground mt-1">
                {result.landmark}
              </h3>
              {(result.city || result.country) && (
                <p className="text-xs text-muted-foreground flex items-center gap-1 mt-1 font-medium">
                  <MapPin className="h-3 w-3 text-coral" />
                  {[result.city, result.country].filter(Boolean).join(", ")}
                </p>
              )}
            </div>

            {result.confidence && (
              <Badge variant="secondary" className="text-xs px-2.5 py-1">
                {(result.confidence * 100).toFixed(1)}% confidence
              </Badge>
            )}
          </div>

          {result.description && (
            <p className="text-xs text-muted-foreground leading-relaxed">
              {result.description}
            </p>
          )}

          <div className="flex flex-wrap gap-2.5 pt-2">
            <Button
              variant="default"
              size="sm"
              onClick={() => handleNavigateToDestination(result)}
              className="flex items-center gap-1.5"
            >
              <span>Explore Destination Guide</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePlanTrip(result.landmark)}
              className="flex items-center gap-1.5"
            >
              <Compass className="h-3.5 w-3.5" />
              <span>Plan Trip Here</span>
            </Button>
          </div>
        </div>
      )}

      {/* Recognition History Section (Strictly separated from recommendations) */}
      {showHistory && (
        <div className="pt-4 border-t border-border/50 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
              <History className="h-4 w-4 text-primary" />
              <span>Landmark Recognition History</span>
            </h3>
            {history.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClearHistory}
                className="text-xs h-7 text-muted-foreground hover:text-red-500 flex items-center gap-1"
              >
                <Trash2 className="h-3 w-3" /> Clear history
              </Button>
            )}
          </div>

          {history.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {history.map((item) => (
                <div
                  key={item.id}
                  className="rounded-xl border border-border/60 bg-muted/20 p-3 flex gap-3 items-center hover:border-primary/40 transition-colors"
                >
                  {item.image && (
                    <img
                      src={item.image}
                      alt={item.name}
                      className="h-14 w-14 rounded-lg object-cover bg-muted shrink-0"
                    />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-sm text-foreground truncate">
                      {item.name}
                    </p>
                    <p className="text-[11px] text-muted-foreground truncate">
                      {[item.city, item.country].filter(Boolean).join(", ")}
                    </p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      {item.timestamp ? new Date(item.timestamp).toLocaleDateString() : ""}
                      {item.confidence ? ` · ${(item.confidence * 100).toFixed(0)}%` : ""}
                    </p>
                  </div>

                  <div className="flex flex-col gap-1 shrink-0">
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-[11px] h-7 px-2"
                      onClick={() => handleNavigateToDestination(item)}
                    >
                      View
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-[11px] h-7 px-2"
                      onClick={() => handlePlanTrip(item.name)}
                    >
                      Plan
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6 rounded-xl border border-dashed border-border/70 text-center text-xs text-muted-foreground">
              No landmark recognition history yet. Photos you detect will appear here.
            </div>
          )}
        </div>
      )}
    </div>
  );
};
