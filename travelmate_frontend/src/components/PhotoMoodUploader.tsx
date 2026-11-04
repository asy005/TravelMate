// src/components/PhotoMoodUploader.tsx
import { useState } from "react";
import { predictPhotoMood } from "@/lib/api";

export default function PhotoMoodUploader({ onResult }: { onResult: (mood: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!file) return;
    setLoading(true);
    try {
      const res = await predictPhotoMood(file);
      if (res.mood) {
        onResult(res.mood);
      } else {
        alert("Error: " + JSON.stringify(res));
      }
    } catch (err: any) {
      alert("Error: " + (err.message || "Failed to analyze photo"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4">
      <input type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      <button
        className="ml-2 bg-primary text-white px-3 py-1 rounded-xl text-sm"
        onClick={submit}
        disabled={loading}
      >
        {loading ? "..." : "Analyze"}
      </button>
    </div>
  );
}
