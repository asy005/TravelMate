import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { MessageCircle, Send, Sparkles, AlertTriangle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useVoiceAssistant } from "@/hooks/useVoiceAssistant";
import {
  VoiceInputButton,
  VoiceStatusBanner,
  SpeechPlaybackControls,
} from "@/components/VoiceControls";
import { LanguageSelector, getStoredLanguage } from "@/components/LanguageSelector";
import { translateText, chatWithBot } from "@/lib/api";

export default function Chatbot() {
  const [searchParams] = useSearchParams();
  const { toast } = useToast();
  const [prompt, setPrompt] = useState("");
  const [reply, setReply] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedLang, setSelectedLang] = useState<string>(getStoredLanguage());
  const [translationError, setTranslationError] = useState<string | null>(null);
  const isSendingRef = useRef(false);

  // Hook up browser Web Speech API with active language support
  const voice = useVoiceAssistant({
    lang: selectedLang,
    onTranscriptComplete: (finalText) => {
      setPrompt((prev) => (prev ? `${prev} ${finalText}` : finalText));
    },
  });

  useEffect(() => {
    const dest = searchParams.get("destination");
    if (dest) {
      setPrompt((prev) => {
        if (!prev || !prev.includes(dest)) {
          return `I want to plan a trip to ${dest}. `;
        }
        return prev;
      });
    }
  }, [searchParams]);

  const handleLanguageChange = (newLang: string) => {
    setSelectedLang(newLang);
    setTranslationError(null);
  };

  const send = async () => {
    if (!prompt.trim() || loading || isSendingRef.current) return;
    isSendingRef.current = true;

    voice.stopListening();
    voice.stopSpeaking();

    setLoading(true);
    setReply("");
    setTranslationError(null);

    try {
      const j = await chatWithBot(prompt);
      let responseText = j.reply || j.error || "No response";

      if (selectedLang !== "en" && responseText) {
        try {
          const trans = await translateText(responseText, selectedLang);
          if (trans.translated_text) {
            responseText = trans.translated_text;
          } else if (trans.error) {
            setTranslationError(`Translation to ${selectedLang.toUpperCase()} failed: ${trans.error}`);
            responseText = `${responseText}\n\n[⚠️ Note: Translation to ${selectedLang.toUpperCase()} failed. Showing English response.]`;
          }
        } catch (err: any) {
          setTranslationError(`Translation service unreachable for ${selectedLang.toUpperCase()}`);
          responseText = `${responseText}\n\n[⚠️ Note: Translation to ${selectedLang.toUpperCase()} failed. Showing English response.]`;
        }
      }

      setReply(responseText);

      // Speak assistant reply if voice output is active and not muted
      if (!voice.isMuted && voice.isSpeechSynthesisSupported && responseText) {
        voice.speak(responseText, selectedLang);
      }
    } catch {
      toast({
        title: "Couldn't reach the assistant",
        description: "Please try again in a moment.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
      isSendingRef.current = false;
    }
  };

  return (
    <div className="min-h-screen container mx-auto px-6 max-w-3xl pt-28 pb-16">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <MessageCircle className="h-6 w-6 text-coral" aria-hidden="true" />
          <h1 className="text-3xl font-bold">TravelMate AI Chat</h1>
        </div>
        <LanguageSelector
          value={selectedLang}
          onChange={handleLanguageChange}
          className="text-xs py-1"
        />
      </div>

      <Card className="p-6 bg-card/95 backdrop-blur-md border border-white/20 animate-fade-up">
        <div className="flex items-center justify-between mb-2">
          <Label htmlFor="chat-prompt">Ask anything about your trip or use voice</Label>
        </div>

        {/* Translation error notification */}
        {translationError && (
          <div className="flex items-center gap-2 p-2.5 mb-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-xs text-amber-600 dark:text-amber-400">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{translationError}</span>
          </div>
        )}

        {/* Voice status & feedback */}
        <VoiceStatusBanner voice={voice} />

        <Textarea
          id="chat-prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
          placeholder={
            selectedLang === "ta"
              ? "எ.கா. கோவா மழைக்கால பயணத்திற்கு நான் என்ன பேக் செய்ய வேண்டும்? (தட்டச்சு செய்யவும் அல்லது பேசவும்)"
              : selectedLang === "kn"
              ? "ಉದಾ. ಗೋವಾ ಪ್ರವಾಸಕ್ಕೆ ನಾನು ಏನನ್ನು ಕೊಂಡೊಯ್ಯಬೇಕು? (ಟೈಪ್ ಮಾಡಿ ಅಥವಾ ಧ್ವನಿ ಬಳಸಿ)"
              : "e.g. What should I pack for a rainy trip to Goa? (Type or click the microphone to speak)"
          }
          className="mt-2 text-base"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              if (e.shiftKey) {
                // Allow Shift+Enter for multiline newline insertion
                return;
              }
              // Submit message without default page scroll or newline
              e.preventDefault();
              e.stopPropagation();
              if (!loading && !isSendingRef.current && prompt.trim()) {
                send();
              }
            }
          }}
        />

        <div className="mt-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <VoiceInputButton voice={voice} disabled={loading} />
            <span className="text-xs text-muted-foreground hidden sm:inline">
              {voice.isListening ? "Listening..." : "Click mic to speak"}
            </span>
          </div>

          <Button variant="hero" onClick={send} disabled={loading || !prompt.trim()}>
            <Send className="h-4 w-4 mr-2" />
            {loading ? "Sending..." : "Send"}
          </Button>
        </div>
      </Card>

      <Card className="mt-5 p-6 bg-card/70 backdrop-blur-md border border-white/10 min-h-[120px]">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
            <Sparkles className="h-3.5 w-3.5 text-coral" /> Reply
          </p>
          {reply && !loading && (
            <SpeechPlaybackControls voice={voice} textToSpeak={reply} />
          )}
        </div>

        {loading ? (
          <p className="text-sm text-muted-foreground animate-pulse">Thinking...</p>
        ) : reply ? (
          <p className="text-sm leading-relaxed animate-fade-up whitespace-pre-wrap">{reply}</p>
        ) : (
          <p className="text-sm text-muted-foreground">Your assistant's reply will appear here.</p>
        )}
      </Card>
    </div>
  );
}
