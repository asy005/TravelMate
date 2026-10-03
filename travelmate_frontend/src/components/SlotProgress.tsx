import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, Circle } from "lucide-react";

const REQUIRED_SLOT_LABELS: Record<string, string> = {
  budget: "Budget",
  duration_days: "Duration",
  travelers: "Travelers",
  travel_style: "Travel style",
};

interface SlotProgressProps {
  slots: Record<string, any>;
  missingSlots: string[];
}

export const SlotProgress = ({ slots, missingSlots }: SlotProgressProps) => {
  const requiredKeys = Object.keys(REQUIRED_SLOT_LABELS);
  const collectedCount = requiredKeys.filter((k) => !missingSlots.includes(k)).length;
  const percent = Math.round((collectedCount / requiredKeys.length) * 100);

  return (
    <div className="bg-card/80 backdrop-blur-md rounded-xl p-4 border border-white/15 mb-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-muted-foreground">
          Gathering your trip details
        </span>
        <span className="text-xs font-semibold text-primary">{percent}%</span>
      </div>
      <Progress value={percent} className="h-1.5 mb-3" />
      <div className="flex flex-wrap gap-2">
        {requiredKeys.map((key) => {
          const done = !missingSlots.includes(key);
          return (
            <Badge
              key={key}
              variant={done ? "default" : "outline"}
              className="flex items-center gap-1 font-normal"
            >
              {done ? (
                <CheckCircle2 className="h-3 w-3" />
              ) : (
                <Circle className="h-3 w-3" />
              )}
              {REQUIRED_SLOT_LABELS[key]}
              {done && slots[key] ? `: ${slots[key]}` : ""}
            </Badge>
          );
        })}
      </div>
    </div>
  );
};
