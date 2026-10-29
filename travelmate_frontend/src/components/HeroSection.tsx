import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Sparkles, Send, MapPin, RotateCcw, Volume2, VolumeX, AlertTriangle } from "lucide-react";
import heroImage from "@/assets/hero-travel.jpg";
import { ChatMessageBubble, ChatMessage } from "@/components/ChatMessageBubble";
import { TypingIndicator } from "@/components/TypingIndicator";
import { SlotProgress } from "@/components/SlotProgress";
import { TripDashboard } from "@/components/TripDashboard";
import {
  sendAssistantMessage,
  getAssistantSession,
  resetAssistantSession,
  translateText,
} from "@/lib/api";
import { useVoiceAssistant } from "@/hooks/useVoiceAssistant";
import {
  VoiceInputButton,
  VoiceStatusBanner,
} from "@/components/VoiceControls";
import { LanguageSelector, getStoredLanguage } from "@/components/LanguageSelector";
import { TopRecommendations } from "@/components/TopRecommendations";

const SESSION_STORAGE_KEY = "travelmate_assistant_session";

const WELCOME_MESSAGE_EN: ChatMessage = {
  role: "assistant",
  content:
    "Hi, I'm your TravelMate AI travel consultant. Tell me a bit about the trip you're dreaming of — where you'd like to go, your budget, who's coming along — and I'll take it from there.",
};

export const HeroSection = () => {
  const [searchParams] = useSearchParams();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE_EN]);
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
  const [selectedLang, setSelectedLang] = useState<string>(getStoredLanguage());
  const [translationError, setTranslationError] = useState<string | null>(null);
  const [currentlySpeakingText, setCurrentlySpeakingText] = useState<string | null>(null);

  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const isSubmittingRef = useRef(false);

  // Hook up Web Speech API Voice Assistant with active language support
  const voice = useVoiceAssistant({
    lang: selectedLang,
    onTranscriptComplete: (finalText) => {
      setInput((prev) => (prev ? `${prev} ${finalText}` : finalText));
    },
  });

  // Resume an existing session on load, if one is stored.
  useEffect(() => {
    const stored = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!stored) return;

    setSessionId(stored);
    getAssistantSession(stored).then((session) => {
      if (!session) return;
      if (session.messages?.length) {
        setMessages([WELCOME_MESSAGE_EN, ...session.messages]);
      }
      setSlots(session.slots || {});
      if (session.plan) setPlan(session.plan);
    });
  }, []);

  // Prefill destination from route search params without losing ability to add dates, budget, etc.
  useEffect(() => {
    const dest = searchParams.get("destination");
    if (dest) {
      setInput((prev) => {
        if (!prev || !prev.includes(dest)) {
          return `I want to plan a trip to ${dest}. `;
        }
        return prev;
      });
      const inputEl = document.getElementById("trip-chat-input");
      if (inputEl) {
        inputEl.focus({ preventScroll: true });
      }
    }
  }, [searchParams]);

  // Keep chat container smoothly scrolled to latest messages without jumping the whole window
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTo({
        top: chatScrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages, isThinking]);

  // Handle switching language: preserves state & preferences, translates welcome / latest message
  const handleLanguageChange = async (newLang: string) => {
    setSelectedLang(newLang);
    setTranslationError(null);

    // If only the welcome message is present and switching from en, translate greeting
    if (messages.length === 1 && messages[0].role === "assistant") {
      if (newLang === "en") {
        setMessages([WELCOME_MESSAGE_EN]);
        return;
      }
      try {
        const trans = await translateText(WELCOME_MESSAGE_EN.content, newLang);
        if (trans.translated_text) {
          setMessages([{ role: "assistant", content: trans.translated_text }]);
        } else if (trans.error) {
          setTranslationError(`Translation to ${newLang.toUpperCase()} failed: ${trans.error}. Showing English.`);
        }
      } catch (err: any) {
        setTranslationError(`Translation to ${newLang.toUpperCase()} service unreachable. Showing English.`);
      }
    }
  };

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isThinking || isSubmittingRef.current) return;
    isSubmittingRef.current = true;

    // Stop active speech recognition or speech output when sending
    voice.stopListening();
    voice.stopSpeaking();

    const userMessage: ChatMessage = { role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsThinking(true);
    setTranslationError(null);

    try {
      const data = await sendAssistantMessage(sessionId, trimmed);

      if (!sessionId) {
        setSessionId(data.session_id);
        localStorage.setItem(SESSION_STORAGE_KEY, data.session_id);
      }

      let replyToDisplay = data.reply;
      let hasTranslationFailed = false;

      // Handle translation if non-English language selected
      if (selectedLang !== "en" && data.reply) {
        try {
          const trans = await translateText(data.reply, selectedLang);
          if (trans.translated_text) {
            replyToDisplay = trans.translated_text;
          } else if (trans.error) {
            hasTranslationFailed = true;
            setTranslationError(`Translation to ${selectedLang.toUpperCase()} failed: ${trans.error}`);
          }
        } catch (err: any) {
          hasTranslationFailed = true;
          setTranslationError(`Translation service error for ${selectedLang.toUpperCase()}`);
        }
      }

      // Explicitly communicate translation failure if non-English was requested
      const finalReplyContent = hasTranslationFailed
        ? `${replyToDisplay}\n\n[⚠️ Note: Translation to ${selectedLang.toUpperCase()} failed. Displaying original English response.]`
        : replyToDisplay;

      // Attach inline destination recommendations to the assistant message when present
      const assistantMsg: import("@/components/ChatMessageBubble").ChatMessage = {
        role: "assistant",
        content: finalReplyContent,
      };
      if (
        data.recommendations &&
        Array.isArray(data.recommendations) &&
        data.recommendations.length > 0
      ) {
        assistantMsg.destinations = data.recommendations;
      }

      setMessages((prev) => [...prev, assistantMsg]);
      setSlots(data.slots || {});
      setMissingSlots(data.missing_slots || []);

      if (data.ready_for_plan && data.plan) {
        setPlan(data.plan);
      }

      // Automatically speak the assistant's reply in selected language if not muted
      if (!voice.isMuted && voice.isSpeechSynthesisSupported && replyToDisplay) {
        setCurrentlySpeakingText(finalReplyContent);
        voice.speak(replyToDisplay, selectedLang);
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
    } finally {
      setIsThinking(false);
      isSubmittingRef.current = false;
    }
  };

  const handleReset = async () => {
    voice.stopSpeaking();
    voice.stopListening();
    if (sessionId) {
      try {
        await resetAssistantSession(sessionId);
      } catch {
        // best-effort
      }
    }
    setMessages([WELCOME_MESSAGE_EN]);
    setSlots({});
    setMissingSlots(["budget", "duration_days", "travelers", "travel_style"]);
    setPlan(null);
    setInput("");
    setCurrentlySpeakingText(null);
    setTranslationError(null);
  };

  const handleSelectRecommendation = (destName: string) => {
    // Preserve existing conversation preferences while selecting this destination.
    // Auto-send the selection so the plan regenerates immediately.
    const promptText = `I want to plan my trip to ${destName}.`;

    // Use a functional update then immediately trigger send with the new text.
    const sendDestination = async (text: string) => {
      if (isThinking || isSubmittingRef.current) return;
      isSubmittingRef.current = true;
      voice.stopListening();
      voice.stopSpeaking();

      const userMessage: import("@/components/ChatMessageBubble").ChatMessage = {
        role: "user",
        content: text,
      };
      setMessages((prev) => [...prev, userMessage]);
      setInput("");
      setIsThinking(true);
      setTranslationError(null);

      try {
        const data = await sendAssistantMessage(sessionId, text);

        if (!sessionId) {
          setSessionId(data.session_id);
          localStorage.setItem(SESSION_STORAGE_KEY, data.session_id);
        }

        let replyToDisplay = data.reply;
        let hasTranslationFailed = false;

        if (selectedLang !== "en" && data.reply) {
          try {
            const trans = await translateText(data.reply, selectedLang);
            if (trans.translated_text) {
              replyToDisplay = trans.translated_text;
            } else if (trans.error) {
              hasTranslationFailed = true;
              setTranslationError(`Translation to ${selectedLang.toUpperCase()} failed: ${trans.error}`);
            }
          } catch {
            hasTranslationFailed = true;
            setTranslationError(`Translation service error for ${selectedLang.toUpperCase()}`);
          }
        }

        const finalReply = hasTranslationFailed
          ? `${replyToDisplay}\n\n[⚠️ Note: Translation to ${selectedLang.toUpperCase()} failed. Displaying original English response.]`
          : replyToDisplay;

        const assistantMsg: import("@/components/ChatMessageBubble").ChatMessage = {
          role: "assistant",
          content: finalReply,
        };
        if (data.recommendations && Array.isArray(data.recommendations) && data.recommendations.length > 0) {
          assistantMsg.destinations = data.recommendations;
        }

        setMessages((prev) => [...prev, assistantMsg]);
        setSlots(data.slots || {});
        setMissingSlots(data.missing_slots || []);

        if (data.ready_for_plan && data.plan) {
          setPlan(data.plan);
        }

        if (!voice.isMuted && voice.isSpeechSynthesisSupported && replyToDisplay) {
          setCurrentlySpeakingText(finalReply);
          voice.speak(replyToDisplay, selectedLang);
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
      } finally {
        setIsThinking(false);
        isSubmittingRef.current = false;
      }
    };

    sendDestination(promptText);

    // Focus chat input without scrolling the whole page
    const inputEl = document.getElementById("trip-chat-input");
    if (inputEl) {
      inputEl.focus({ preventScroll: true });
    }
  };

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter") {
      if (e.shiftKey) {
        // Shift+Enter allows newline in multiline text
        return;
      }
      // Submit without unexpected whole-page scroll or default form behavior
      e.preventDefault();
      e.stopPropagation();
      if (!isThinking && !isSubmittingRef.current && input.trim()) {
        handleSend();
      }
    }
  };

  return (
    <section className="relative flex flex-col items-center justify-start pt-20 pb-10 overflow-hidden">
      {/* BG */}
      <div className="absolute inset-0">
        <img src={heroImage} className="w-full h-full object-cover" alt="Travel background" />
        <div className="absolute inset-0 bg-gradient-to-b from-background/20 via-background/40 to-background/60" />
      </div>

      {/* MAIN CONTENT */}
      <div className="relative z-10 container mx-auto px-4 sm:px-6 max-w-4xl space-y-4 sm:space-y-5">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2 sm:gap-3 mb-1 sm:mb-2">
          <MapPin className="h-8 w-8 sm:h-9 sm:w-9 text-primary" />
          <h1 className="text-4xl sm:text-5xl font-bold bg-gradient-to-r from-primary via-sky to-coral bg-clip-text text-transparent">
            TravelMate
          </h1>
        </div>

        {/* Chat Card */}
        <div className="bg-card/95 backdrop-blur-md rounded-2xl p-4 sm:p-6 shadow-xl border border-white/20">
          <div className="flex items-center justify-between mb-3 sm:mb-4 flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 sm:h-6 sm:w-6 text-coral" />
              <h2 className="text-xl sm:text-2xl font-semibold">Plan my trip</h2>
            </div>
            <div className="flex items-center gap-2">
              <LanguageSelector
                value={selectedLang}
                onChange={handleLanguageChange}
                className="text-xs py-1"
              />
              {voice.isSpeechSynthesisSupported && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={voice.toggleMute}
                  className="text-muted-foreground h-8 text-xs"
                  title={voice.isMuted ? "Turn on automatic speech for assistant replies" : "Turn off automatic speech"}
                  aria-label={voice.isMuted ? "Turn on auto-speech" : "Turn off auto-speech"}
                >
                  {voice.isMuted ? (
                    <>
                      <VolumeX className="h-3.5 w-3.5 mr-1 text-muted-foreground" />
                      Auto-Voice: Off
                    </>
                  ) : (
                    <>
                      <Volume2 className="h-3.5 w-3.5 mr-1 text-coral" />
                      Auto-Voice: On
                    </>
                  )}
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={handleReset}
                className="text-muted-foreground h-8 text-xs"
              >
                <RotateCcw className="h-3.5 w-3.5 mr-1" /> Start over
              </Button>
            </div>
          </div>

          <SlotProgress slots={slots} missingSlots={missingSlots} />

          {/* Translation error banner if translation failed */}
          {translationError && (
            <div className="flex items-center gap-2 p-2.5 mb-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-xs text-amber-600 dark:text-amber-400">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{translationError}</span>
            </div>
          )}

          {/* Conversation with scoped container scrolling */}
          <div
            ref={chatScrollRef}
            className="max-h-[380px] sm:max-h-[420px] overflow-y-auto space-y-3 sm:space-y-4 pr-1 mb-3"
            role="log"
            aria-live="polite"
            aria-label="Conversation with AI travel assistant"
          >
            {messages.map((m, i) => (
              <ChatMessageBubble
                key={i}
                message={m}
                onSpeak={(text) => {
                  setCurrentlySpeakingText(text);
                  voice.clearError();
                  voice.speak(text, selectedLang, { force: true });
                }}
                isSpeaking={voice.isSpeaking && currentlySpeakingText === m.content}
                onStopSpeak={() => {
                  voice.stopSpeaking();
                  setCurrentlySpeakingText(null);
                }}
                onSelectDestination={handleSelectRecommendation}
              />
            ))}
            {isThinking && <TypingIndicator />}
          </div>

          {/* Voice Status & Error Feedback */}
          <VoiceStatusBanner voice={voice} />

          {/* Input & Voice Controls */}
          <div className="flex items-center gap-2 sm:gap-3">
            <label htmlFor="trip-chat-input" className="sr-only">
              Describe your trip to the AI assistant
            </label>
            <Textarea
              id="trip-chat-input"
              rows={1}
              placeholder={
                selectedLang === "ta"
                  ? "உங்கள் பயண திட்டத்தை விவரிக்கவும் அல்லது குரலை பயன்படுத்தவும்... (Shift+Enter புதிய வரி)"
                  : selectedLang === "kn"
                  ? "ನಿಮ್ಮ ಪ್ರವಾಸದ ಯೋಜನೆಯನ್ನು ತಿಳಿಸಿ ಅಥವಾ ಧ್ವನಿಯನ್ನು ಬಳಸಿ... (Shift+Enter ಹೊಸ ಸಾಲು)"
                  : "Tell me about your trip or use voice... (Shift+Enter for newline)"
              }
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="flex-1 min-h-[48px] max-h-28 text-base rounded-xl py-3 resize-none leading-normal"
              onKeyDown={handleInputKeyDown}
              disabled={isThinking}
            />

            {/* Voice Input Button */}
            <VoiceInputButton voice={voice} disabled={isThinking} />

            <Button
              variant="hero"
              size="lg"
              onClick={handleSend}
              disabled={isThinking || !input.trim() || isSubmittingRef.current}
              className="h-12 px-5 sm:px-8 rounded-xl shrink-0"
              aria-label="Send message"
            >
              <Send className="h-5 w-5" aria-hidden="true" />
            </Button>
          </div>
        </div>

        {/* Top-Three Ranked Recommendations */}
        <TopRecommendations
          slots={slots}
          onSelect={handleSelectRecommendation}
        />

        {/* Generated Plan */}
        {plan && (
          <div className="mt-6">
            <TripDashboard plan={plan} sessionId={sessionId} />
          </div>
        )}
      </div>
    </section>
  );
};
