// src/components/PhotoMoodUploader.tsx
import { useState } from "react";

export default function PhotoMoodUploader({ onResult }: { onResult: (mood:string)=>void }) {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!file) return;
    setLoading(true);
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("http://127.0.0.1:8000/photo/mood", { method: "POST", body: fd });
    const j = await res.json();
    setLoading(false);
    if (j.mood) onResult(j.mood);
    else alert("Error: " + JSON.stringify(j));
  };

  return (
    <div className="p-4">
      <input type="file" accept="image/*" onChange={(e)=> setFile(e.target.files?.[0] || null)} />
      <button className="ml-2 bg-primary text-white px-3 py-1 rounded" onClick={submit} disabled={loading}>{loading ? "..." : "Analyze"}</button>
    </div>
  );
}
