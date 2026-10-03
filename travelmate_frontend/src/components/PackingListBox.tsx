import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Backpack } from "lucide-react";

export const PackingListBox = ({ destination }: { destination: string }) => {
  const [days, setDays] = useState(3);
  const [weather, setWeather] = useState("");
  const [activities, setActivities] = useState("");
  const [packingList, setPackingList] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const generateList = async () => {
    setLoading(true);

    const body = {
      destination,
      days,
      weather,
      activities: activities.split(",").map((x) => x.trim()),
    };

    const res = await fetch("http://127.0.0.1:8000/packing/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    setPackingList(data.packing_list);
    setLoading(false);
  };

  return (
    <div className="bg-white rounded-xl p-6 shadow-md border">
      <h2 className="text-xl font-semibold mb-3 flex items-center gap-2">
        <Backpack /> Packing List
      </h2>

      <div className="flex gap-4 mb-4">
        <Input
          type="number"
          min={1}
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          placeholder="Days"
        />
        <Input
          placeholder="Weather (hot, cold, rain...)"
          value={weather}
          onChange={(e) => setWeather(e.target.value)}
        />
      </div>

      <Input
        placeholder="Activities (hiking, swim, dinner...)"
        value={activities}
        onChange={(e) => setActivities(e.target.value)}
      />

      <Button className="mt-4" onClick={generateList} disabled={loading}>
        {loading ? <Loader2 className="animate-spin" /> : "Generate Packing List"}
      </Button>

      <ul className="mt-4 space-y-2">
        {packingList.map((item, i) => (
          <li key={i} className="bg-secondary p-3 rounded-md">
            🧳 {item}
          </li>
        ))}
      </ul>
    </div>
  );
};
