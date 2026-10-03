import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sparkles, Send, MapPin, RotateCcw } from "lucide-react";
import heroImage from "@/assets/hero-travel.jpg";
import { ChatMessageBubble, ChatMessage } from "@/components/ChatMessageBubble";
import { TypingIndicator } from "@/components/TypingIndicator";
import { SlotProgress } from "@/components/SlotProgress";
import { TripDashboard } from "@/components/TripDashboard";
import {
  sendAssistantMessage,
  getAssistantSession,
  resetAssistantSession,
} from "@/lib/api";

const SESSION_STORAGE_KEY = "travelmate_assistant_session";

const WELCOME_MESSAGE: ChatMessage = {
  role: "assistant",
  content:
    "Hi, I'm your TravelMate AI travel consultant. Tell me a bit about the trip you're dreaming of — where you'd like to go, your budget, who's coming along — and I'll take it from there.",
};

export const HeroSection = () => {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [slots, setSlots] = useState<Record<string, any>>({});
  const [missingSlots, setMissingSlots] = useState<string[]>([
    "budget",
    "duration_days",
    "travelers",
    "travel_style",
  ]);
  const [plan, setPlan] = useState<Record<string, any> | null>(null);

  const bottomRef = useRef<HTMLDivElement | null>(null);

  // Resume an existing session on load, if one is stored.
  useEffect(() => {
    const stored = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!stored) return;

    setSessionId(stored);
    getAssistantSession(stored).then((session) => {
      if (!session) return;
      if (session.messages?.length) {
        setMessages([WELCOME_MESSAGE, ...session.messages]);
      }
      setSlots(session.slots || {});
      if (session.plan) setPlan(session.plan);
    });
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking, plan]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isThinking) return;

    const userMessage: ChatMessage = { role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsThinking(true);

    try {
      const data = await sendAssistantMessage(sessionId, trimmed);

      if (!sessionId) {
        setSessionId(data.session_id);
        localStorage.setItem(SESSION_STORAGE_KEY, data.session_id);
      }

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply },
      ]);
      setSlots(data.slots || {});
      setMissingSlots(data.missing_slots || []);

      if (data.ready_for_plan && data.plan) {
        setPlan(data.plan);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "Sorry, I'm having trouble reaching the planning engine right now — please try again in a moment.",
        },
      ]);
    }

    setIsThinking(false);
  };

  const handleReset = async () => {
    if (sessionId) {
      try {
        await resetAssistantSession(sessionId);
      } catch {
        // best-effort — still clear local state below
      }
    }
    setMessages([WELCOME_MESSAGE]);
    setSlots({});
    setMissingSlots(["budget", "duration_days", "travelers", "travel_style"]);
    setPlan(null);
    setInput("");
  };

  return (
    <section className="relative min-h-screen flex flex-col items-center justify-start py-20 overflow-hidden">
      {/* BG */}
      <div className="absolute inset-0">
        <img src={heroImage} className="w-full h-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-b from-background/20 via-background/40 to-background/60" />
      </div>

      {/* MAIN CONTENT */}
      <div className="relative z-10 container mx-auto px-6 max-w-4xl">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <MapPin className="h-10 w-10 text-primary" />
          <h1 className="text-6xl font-bold bg-gradient-to-r from-primary via-sky to-coral bg-clip-text text-transparent">
            TravelMate
          </h1>
        </div>

        {/* Chat Card */}
        <div className="bg-card/95 backdrop-blur-md rounded-2xl p-6 shadow-xl border border-white/20">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Sparkles className="h-6 w-6 text-coral" />
              <h2 className="text-2xl font-semibold">Plan my trip</h2>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleReset}
              className="text-muted-foreground"
            >
              <RotateCcw className="h-4 w-4 mr-1" /> Start over
            </Button>
          </div>

          <SlotProgress slots={slots} missingSlots={missingSlots} />

          {/* Conversation */}
          <div
            className="max-h-[420px] overflow-y-auto space-y-4 pr-1 mb-4"
            role="log"
            aria-live="polite"
            aria-label="Conversation with AI travel assistant"
          >
            {messages.map((m, i) => (
              <ChatMessageBubble key={i} message={m} />
            ))}
            {isThinking && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="flex gap-3">
            <label htmlFor="trip-chat-input" className="sr-only">
              Describe your trip to the AI assistant
            </label>
            <Input
              id="trip-chat-input"
              placeholder="Tell me about your trip..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="flex-1 h-12 text-base rounded-xl"
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              disabled={isThinking}
            />
            <Button
              variant="hero"
              size="lg"
              onClick={handleSend}
              disabled={isThinking || !input.trim()}
              className="h-12 px-8 rounded-xl"
              aria-label="Send message"
            >
              <Send className="h-5 w-5" aria-hidden="true" />
            </Button>
          </div>
        </div>

        {/* Generated Plan */}
        {plan && (
          <div className="mt-8">
            <TripDashboard plan={plan} sessionId={sessionId} />
          </div>
        )}
      </div>
    </section>
  );
};
