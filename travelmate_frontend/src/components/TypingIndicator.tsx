import { Sparkles } from "lucide-react";

export const TypingIndicator = () => {
  return (
    <div className="flex items-start gap-3 animate-fade-up">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-coral/20 text-coral">
        <Sparkles className="h-4 w-4" />
      </div>
      <div className="flex items-center gap-1 rounded-2xl rounded-tl-sm bg-card/95 backdrop-blur-md border border-white/20 px-4 py-3 shadow-sm">
        <span className="h-2 w-2 rounded-full bg-muted-foreground/60 animate-bounce [animation-delay:-0.3s]" />
        <span className="h-2 w-2 rounded-full bg-muted-foreground/60 animate-bounce [animation-delay:-0.15s]" />
        <span className="h-2 w-2 rounded-full bg-muted-foreground/60 animate-bounce" />
      </div>
    </div>
  );
};
