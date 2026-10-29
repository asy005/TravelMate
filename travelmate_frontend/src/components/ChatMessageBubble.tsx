import { Sparkles, User, Volume2, Square, MapPin, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  ts?: string;
  /** Inline destination recommendations to display as clickable cards. */
  destinations?: Array<{
    id: number;
    name: string;
    state?: string;
    category?: string;
    average_budget?: number;
    ideal_duration?: number;
    thumbnail_url?: string;
    match_label?: string;
    explanation?: string;
  }>;
}

export interface ChatMessageBubbleProps {
  message: ChatMessage;
  onSpeak?: (text: string) => void;
  isSpeaking?: boolean;
  onStopSpeak?: () => void;
  /** Called when a destination card is clicked; receives the destination name. */
  onSelectDestination?: (destinationName: string) => void;
}

const DEFAULT_IMG =
  "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&q=80&w=800";

const MATCH_COLORS: Record<string, string> = {
  "Top Match": "bg-amber-500 text-white",
  "Great Match": "bg-slate-400 text-white",
  "Recommended Match": "bg-amber-700 text-white",
};

export const ChatMessageBubble = ({
  message,
  onSpeak,
  isSpeaking = false,
  onStopSpeak,
  onSelectDestination,
}: ChatMessageBubbleProps) => {
  const isUser = message.role === "user";
  const hasDestinations =
    !isUser &&
    Array.isArray(message.destinations) &&
    message.destinations.length > 0;

  return (
    <div
      className={cn(
        "flex items-start gap-3 animate-fade-up",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-primary/20 text-primary" : "bg-coral/20 text-coral"
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
      </div>

      <div
        className={cn(
          "rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm",
          hasDestinations
            ? "w-full max-w-[95%]"
            : "max-w-[80%]",
          isUser
            ? "bg-primary text-primary-foreground rounded-tr-sm"
            : "bg-card/95 backdrop-blur-md border border-white/20 rounded-tl-sm"
        )}
      >
        <div>{message.content}</div>

        {/* ── Inline destination recommendation cards ── */}
        {hasDestinations && (
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
            {message.destinations!.map((dest, idx) => {
              const matchLabel =
                dest.match_label ||
                (idx === 0 ? "Top Match" : idx === 1 ? "Great Match" : "Recommended Match");
              const badgeColor =
                MATCH_COLORS[matchLabel] || "bg-primary text-white";
              const imgSrc = dest.thumbnail_url
                ? dest.thumbnail_url.startsWith("http")
                  ? dest.thumbnail_url
                  : `http://127.0.0.1:8000${dest.thumbnail_url}`
                : DEFAULT_IMG;

              return (
                <div
                  key={dest.id || `${dest.name}-${idx}`}
                  className="group relative bg-background/60 hover:bg-background/90 rounded-xl border border-white/10 hover:border-coral/50 overflow-hidden shadow-sm hover:shadow-md transition-all flex flex-col cursor-pointer"
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectDestination?.(dest.name)}
                  onKeyDown={(e) => e.key === "Enter" && onSelectDestination?.(dest.name)}
                  aria-label={`Plan trip to ${dest.name}`}
                >
                  {/* Image */}
                  <div className="relative h-28 w-full overflow-hidden bg-muted">
                    <img
                      src={imgSrc}
                      alt={dest.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                      onError={(e) => {
                        (e.target as HTMLImageElement).src = DEFAULT_IMG;
                      }}
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent" />
                    <span
                      className={`absolute top-2 left-2 text-[10px] font-bold px-1.5 py-0.5 rounded shadow-sm ${badgeColor}`}
                    >
                      {matchLabel}
                    </span>
                    <div className="absolute bottom-2 left-2 right-2 text-white">
                      <h4 className="font-bold text-sm leading-tight drop-shadow-sm group-hover:text-coral transition-colors">
                        {dest.name}
                      </h4>
                      {dest.state && (
                        <p className="text-[10px] text-white/80 flex items-center gap-0.5 mt-0.5">
                          <MapPin className="h-2.5 w-2.5 text-coral shrink-0" />
                          {dest.state}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Body */}
                  <div className="p-2.5 flex-1 flex flex-col justify-between space-y-2">
                    {dest.explanation && (
                      <p className="text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
                        {dest.explanation}
                      </p>
                    )}
                    <div className="flex items-center justify-between gap-1 text-[10px] pt-1.5 border-t border-white/10">
                      {dest.category && (
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
                          {dest.category}
                        </Badge>
                      )}
                      {dest.average_budget != null && (
                        <span className="font-semibold text-foreground">
                          ₹{Math.round(dest.average_budget).toLocaleString("en-IN")}
                        </span>
                      )}
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      className="w-full text-[11px] h-6 flex items-center justify-center gap-1 group-hover:bg-coral group-hover:text-white transition-colors"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectDestination?.(dest.name);
                      }}
                    >
                      Plan this trip <ArrowRight className="h-2.5 w-2.5" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {!isUser && onSpeak && (
          <div className="mt-2 pt-1.5 border-t border-white/10 flex items-center gap-2">
            {isSpeaking ? (
              <button
                type="button"
                onClick={onStopSpeak}
                className="inline-flex items-center gap-1 text-xs text-destructive hover:opacity-80 transition-opacity"
                title="Stop speaking"
                aria-label="Stop speaking"
              >
                <Square className="h-3 w-3 fill-current" /> Stop
              </button>
            ) : (
              <button
                type="button"
                onClick={() => onSpeak(message.content)}
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors"
                title="Listen to message"
                aria-label="Listen to message"
              >
                <Volume2 className="h-3 w-3" /> Listen
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
