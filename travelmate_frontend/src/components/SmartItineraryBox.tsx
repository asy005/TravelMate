import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, Calendar } from "lucide-react";

export const SmartItineraryBox = ({ destination }: { destination: string }) => {
  const [days, setDays] = useState(3);
  const [plan, setPlan] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);

  const generatePlan = async () => {
    setLoading(true);

    const res = await fetch("http://127.0.0.1:8000/plan/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ destination, days }),
    });

    const data = await res.json();
    setPlan(data.plan);
    setLoading(false);
  };

  return (
    <div className="bg-white rounded-xl p-6 shadow-md border">
      <h2 className="text-xl font-semibold mb-3 flex items-center gap-2">
        <Calendar /> Smart Itinerary
      </h2>

      <input
        type="number"
        min={1}
        className="p-2 border rounded-md w-32"
        value={days}
        onChange={(e) => setDays(Number(e.target.value))}
      />

      <Button className="mt-4" onClick={generatePlan} disabled={loading}>
        {loading ? <Loader2 className="animate-spin" /> : "Generate Itinerary"}
      </Button>

      {plan && (
        <div className="mt-6 space-y-4">
          {Object.keys(plan).map((day) => (
            <div key={day} className="bg-secondary p-4 rounded-md">
              <h3 className="font-semibold text-lg mb-2">
                📅 {day.replace("_", " ").toUpperCase()}
              </h3>
              <ul className="space-y-1">
                {plan[day].map((act: string, i: number) => (
                  <li key={i}>• {act}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
