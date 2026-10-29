import { useState, useEffect, useRef, useCallback } from "react";

// SpeechRecognition type definitions for cross-browser Web Speech API
interface IWindowSpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

export interface VoiceAssistantState {
  isListening: boolean;
  isProcessing: boolean;
  isSpeaking: boolean;
  isMuted: boolean;
  transcript: string;
  interimTranscript: string;
  error: string | null;
  voiceNotice: string | null;
  activeLanguage: string;
  availableVoices: SpeechSynthesisVoice[];
  isSpeechRecognitionSupported: boolean;
  isSpeechSynthesisSupported: boolean;
  startListening: (langOverride?: string) => void;
  stopListening: () => void;
  speak: (text: string, langOverride?: string, options?: { force?: boolean }) => void;
  retrySpeak: () => void;
  stopSpeaking: () => void;
  toggleMute: () => void;
  clearError: () => void;
  clearNotice: () => void;
}

/**
 * Maps ISO 639-1 language codes (e.g. 'ta', 'kn', 'hi', 'en') to BCP 47 speech tags.
 */
export function getBcp47Language(langCode: string = "en"): string {
  const normalized = (langCode || "en").toLowerCase().trim();
  const map: Record<string, string> = {
    en: "en-IN",
    hi: "hi-IN",
    ta: "ta-IN",
    kn: "kn-IN",
    te: "te-IN",
    bn: "bn-IN",
    mr: "mr-IN",
    gu: "gu-IN",
    ml: "ml-IN",
    pa: "pa-IN",
    fr: "fr-FR",
    de: "de-DE",
    es: "es-ES",
    ja: "ja-JP",
    zh: "zh-CN",
    ar: "ar-SA",
    ru: "ru-RU",
  };
  return map[normalized] || normalized;
}

export interface VoiceSelectionResult {
  voice: SpeechSynthesisVoice | null;
  langTag: string;
  isNativeVoice: boolean;
  notice: string | null;
}

/**
 * Selects the best voice for the target language.
 * Checks for native language voices; if unavailable, provides clear notification and fallback.
 */
export function selectVoiceForLanguage(
  voices: SpeechSynthesisVoice[],
  targetLangCode: string = "en"
): VoiceSelectionResult {
  const normalized = (targetLangCode || "en").toLowerCase().trim();
  const bcp47 = getBcp47Language(normalized);
  const langPrefix = normalized;

  const langNames: Record<string, string> = {
    ta: "Tamil",
    kn: "Kannada",
    en: "English",
    hi: "Hindi",
  };
  const langLabel = langNames[normalized] || normalized.toUpperCase();

  if (!voices || voices.length === 0) {
    return {
      voice: null,
      langTag: bcp47,
      isNativeVoice: false,
      notice: null,
    };
  }

  // Look for matching voices in the target language (e.g. ta-IN or kn-IN or prefix 'ta', 'kn')
  const matchingVoices = voices.filter((v) => {
    const vLang = (v.lang || "").toLowerCase().replace("_", "-");
    return vLang === bcp47.toLowerCase() || vLang.startsWith(`${langPrefix}-`) || vLang === langPrefix;
  });

  if (matchingVoices.length > 0) {
    // Prefer Indian regional voice if available
    const indianVoice = matchingVoices.find((v) =>
      (v.lang || "").toLowerCase().includes("in")
    );
    // Natural / female voices
    const naturalVoice = matchingVoices.find((v) =>
      /female|sangeeta|kalpana|heera|zira|natural|google/i.test(v.name)
    );
    const chosen = indianVoice || naturalVoice || matchingVoices[0];
    return {
      voice: chosen,
      langTag: chosen.lang || bcp47,
      isNativeVoice: true,
      notice: null,
    };
  }

  // Target voice not installed in browser (common on Windows for Tamil / Kannada)
  const isEnglishTarget = normalized === "en";
  const defaultVoice = voices.find((v) => v.default) || voices.find((v) => (v.lang || "").toLowerCase().startsWith("en")) || voices[0];

  let notice: string | null = null;
  if (!isEnglishTarget) {
    notice = `${langLabel} voice is not installed in this browser. Playing using available system voice.`;
  }

  return {
    voice: defaultVoice || null,
    // Use fallback voice's own language tag so the TTS engine does not reject the utterance
    langTag: defaultVoice?.lang || "en-IN",
    isNativeVoice: isEnglishTarget,
    notice,
  };
}

export function cleanSpeechText(text: string): string {
  if (!text) return "";
  let cleaned = text;

  // Remove code blocks and inline code
  cleaned = cleaned.replace(/```[\s\S]*?```/g, "");
  cleaned = cleaned.replace(/`([^`]+)`/g, "$1");

  // Remove markdown links [text](url) -> text
  cleaned = cleaned.replace(/\[([^\]]+)\]\([^\)]+\)/g, "$1");

  // Remove URLs
  cleaned = cleaned.replace(/https?:\/\/\S+/g, "");

  // Remove markdown headers
  cleaned = cleaned.replace(/^#{1,6}\s+/gm, "");

  // Remove bold / italic markers
  cleaned = cleaned.replace(/\*{1,3}([^*]+)\*{1,3}/g, "$1");
  cleaned = cleaned.replace(/_{1,3}([^_]+)_{1,3}/g, "$1");

  // Remove bullet points
  cleaned = cleaned.replace(/^\s*[-*•]\s+/gm, "");
  cleaned = cleaned.replace(/^\s*\d+\.\s+/gm, "");

  // Convert Indian Rupee symbols to spoken words
  cleaned = cleaned.replace(/₹\s*(\d[\d,]*)/g, "$1 rupees");
  cleaned = cleaned.replace(/rs\.?\s*(\d[\d,]*)/gi, "$1 rupees");

  // Clean whitespace
  cleaned = cleaned.replace(/\n+/g, " ");
  cleaned = cleaned.replace(/\s{2,}/g, " ");

  return cleaned.trim();
}

export function useVoiceAssistant(options?: {
  onTranscriptComplete?: (finalText: string) => void;
  autoSpeakReplies?: boolean;
  lang?: string;
}): VoiceAssistantState {
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isMuted, setIsMuted] = useState<boolean>(() => {
    try {
      return localStorage.getItem("travelmate_voice_muted") === "true";
    } catch {
      return false;
    }
  });
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [voiceNotice, setVoiceNotice] = useState<string | null>(null);
  const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([]);

  const activeLang = options?.lang || "en";
  const recognitionRef = useRef<IWindowSpeechRecognition | null>(null);
  // Retain active utterance reference to prevent Chromium garbage collection bug
  const activeUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const chunksQueueRef = useRef<{ chunks: string[]; voice: SpeechSynthesisVoice | null; langTag: string } | null>(null);
  const lastSpokenRef = useRef<{ text: string; lang?: string } | null>(null);

  const isSpeechRecognitionSupported =
    typeof window !== "undefined" &&
    !!(
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition
    );

  const isSpeechSynthesisSupported =
    typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    "SpeechSynthesisUtterance" in window;

  // Load voices and listen for voiceschanged event
  useEffect(() => {
    if (!isSpeechSynthesisSupported) return;

    const updateVoices = () => {
      try {
        const voices = window.speechSynthesis.getVoices();
        if (voices && voices.length > 0) {
          setAvailableVoices(voices);
        }
      } catch (err) {
        console.warn("[VoiceAssistant] Error loading voices:", err);
      }
    };

    updateVoices();
    window.speechSynthesis.addEventListener("voiceschanged", updateVoices);
    const fallbackTimer = setTimeout(updateVoices, 300);

    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", updateVoices);
      clearTimeout(fallbackTimer);
    };
  }, [isSpeechSynthesisSupported]);

  // Cleanup speech synthesis on unmount
  useEffect(() => {
    return () => {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
        activeUtteranceRef.current = null;
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // ignore cleanup abort errors
        }
      }
    };
  }, []);

  const clearError = useCallback(() => setError(null), []);
  const clearNotice = useCallback(() => setVoiceNotice(null), []);

  const stopSpeaking = useCallback(() => {
    chunksQueueRef.current = null;
    if (isSpeechSynthesisSupported) {
      window.speechSynthesis.cancel();
      activeUtteranceRef.current = null;
    }
    setIsSpeaking(false);
  }, [isSpeechSynthesisSupported]);

  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const next = !prev;
      if (next && isSpeechSynthesisSupported) {
        chunksQueueRef.current = null;
        window.speechSynthesis.cancel();
        activeUtteranceRef.current = null;
        setIsSpeaking(false);
      }
      try {
        localStorage.setItem("travelmate_voice_muted", String(next));
      } catch {
        // ignore storage errors
      }
      return next;
    });
  }, [isSpeechSynthesisSupported]);

  const speakNextChunk = useCallback(() => {
    if (!chunksQueueRef.current || chunksQueueRef.current.chunks.length === 0) {
      activeUtteranceRef.current = null;
      setIsSpeaking(false);
      return;
    }

    const { chunks, voice, langTag } = chunksQueueRef.current;
    const nextText = chunks.shift();
    if (!nextText) {
      activeUtteranceRef.current = null;
      setIsSpeaking(false);
      return;
    }

    const utterance = new SpeechSynthesisUtterance(nextText);
    utterance.lang = langTag;
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    if (voice) utterance.voice = voice;

    utterance.onstart = () => {
      setIsSpeaking(true);
      setError(null);
    };

    utterance.onend = () => {
      // Speak next sentence chunk
      if (chunksQueueRef.current && chunksQueueRef.current.chunks.length > 0) {
        speakNextChunk();
      } else {
        activeUtteranceRef.current = null;
        chunksQueueRef.current = null;
        setIsSpeaking(false);
      }
    };

    utterance.onerror = (e) => {
      activeUtteranceRef.current = null;
      chunksQueueRef.current = null;
      setIsSpeaking(false);
      if (e.error !== "canceled" && e.error !== "interrupted") {
        console.warn("[VoiceAssistant] TTS error:", e.error);
        if (e.error === "synthesis-failed") {
          setError("Speech playback failed. Click 'Retry' to play audio again.");
        } else if (e.error === "not-allowed") {
          setError("Audio playback paused by browser. Click 'Listen' on message to hear response.");
        } else {
          setError(`Speech playback issue (${e.error}). Click 'Retry' to try again.`);
        }
      }
    };

    activeUtteranceRef.current = utterance;
    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
    }
    window.speechSynthesis.speak(utterance);
  }, []);

  const speak = useCallback(
    (text: string, langOverride?: string, speakOptions?: { force?: boolean }) => {
      if (!isSpeechSynthesisSupported) {
        setError("Text-to-speech is not supported in this browser.");
        return;
      }

      // If user manually clicked "Listen", force=true bypasses the auto-speech mute setting
      const isManual = speakOptions?.force ?? false;
      if (!isManual && isMuted) {
        return;
      }

      if (!text || !text.trim()) {
        return;
      }

      try {
        const cleaned = cleanSpeechText(text);
        if (!cleaned) return;

        const targetLangCode = langOverride || activeLang || "en";
        lastSpokenRef.current = { text: cleaned, lang: targetLangCode };

        const currentVoices = availableVoices.length > 0 ? availableVoices : (typeof window !== "undefined" && "speechSynthesis" in window ? window.speechSynthesis.getVoices() : []);
        const { voice, langTag, notice } = selectVoiceForLanguage(currentVoices, targetLangCode);

        if (notice) {
          setVoiceNotice(notice);
        } else {
          setVoiceNotice(null);
        }

        // Cancel previous speech safely to avoid overlapping audio
        chunksQueueRef.current = null;
        if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
          window.speechSynthesis.cancel();
        }

        // Split into chunks of ~150 chars by sentence boundaries to prevent synthesis-failed on long text
        const rawSentences = cleaned.match(/[^.!?\n]+[.!?\n]+|[^.!?\n]+$/g) || [cleaned];
        const chunks: string[] = [];
        let buffer = "";
        for (const s of rawSentences) {
          const trimmed = s.trim();
          if (!trimmed) continue;
          if ((buffer + " " + trimmed).length < 160) {
            buffer = (buffer + " " + trimmed).trim();
          } else {
            if (buffer) chunks.push(buffer);
            buffer = trimmed;
          }
        }
        if (buffer) chunks.push(buffer);
        const finalChunks = chunks.length > 0 ? chunks : [cleaned];

        chunksQueueRef.current = { chunks: finalChunks, voice, langTag };

        // Allow cancel() to settle before speaking
        setTimeout(() => {
          speakNextChunk();
        }, 60);
      } catch (err: any) {
        console.warn("[VoiceAssistant] Failed to speak utterance:", err);
        setIsSpeaking(false);
        setError("Failed to start speech playback. Please try again.");
      }
    },
    [isSpeechSynthesisSupported, isMuted, activeLang, availableVoices, speakNextChunk]
  );

  const retrySpeak = useCallback(() => {
    if (!lastSpokenRef.current || !isSpeechSynthesisSupported) return;
    setError(null);
    stopSpeaking();
    setTimeout(() => {
      if (lastSpokenRef.current) {
        speak(lastSpokenRef.current.text, lastSpokenRef.current.lang, { force: true });
      }
    }, 100);
  }, [isSpeechSynthesisSupported, stopSpeaking, speak]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
    }
    setIsListening(false);
    setIsProcessing(false);
  }, []);

  const startListening = useCallback(
    (langOverride?: string) => {
      if (!isSpeechRecognitionSupported) {
        setError(
          "Voice input is not supported in this browser. Please use text input or open in Chrome, Edge, or Safari."
        );
        return;
      }

      // Cancel any active speech synthesis before listening so microphone does not pick it up
      stopSpeaking();
      setError(null);
      setTranscript("");
      setInterimTranscript("");

      const SpeechRecognitionClass =
        (window as any).SpeechRecognition ||
        (window as any).webkitSpeechRecognition;

      const recognition: IWindowSpeechRecognition = new SpeechRecognitionClass();
      recognition.continuous = false;
      recognition.interimResults = true;

      const targetLangCode = langOverride || activeLang || "en";
      recognition.lang = getBcp47Language(targetLangCode);

      recognition.onstart = () => {
        setIsListening(true);
        setIsProcessing(false);
        setError(null);
      };

      recognition.onresult = (event: any) => {
        let interim = "";
        let final = "";

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const item = event.results[i];
          if (item.isFinal) {
            final += item[0].transcript;
          } else {
            interim += item[0].transcript;
          }
        }

        if (interim) {
          setInterimTranscript(interim);
        }

        if (final) {
          const trimmed = final.trim();
          if (trimmed) {
            setTranscript(trimmed);
            setInterimTranscript("");
            setIsProcessing(true);
            if (options?.onTranscriptComplete) {
              options.onTranscriptComplete(trimmed);
            }
          }
        }
      };

      recognition.onerror = (event: any) => {
        const errCode = event.error;
        setIsListening(false);
        setIsProcessing(false);

        if (errCode === "not-allowed" || errCode === "permission-denied") {
          setError(
            "Microphone permission was denied. Spoken audio playback is still available using the 'Listen' button."
          );
        } else if (errCode === "no-speech") {
          setError("No speech was detected. Please try speaking again or use text input.");
        } else if (errCode === "audio-capture") {
          setError("No microphone was detected. Please connect an audio input device.");
        } else if (errCode === "network") {
          setError(
            "Speech recognition network error. Please verify your connection or continue with text input."
          );
        } else if (errCode !== "aborted") {
          setError(`Speech recognition issue (${errCode}). Please try again or use text.`);
        }
      };

      recognition.onend = () => {
        setIsListening(false);
        setIsProcessing(false);
      };

      recognitionRef.current = recognition;

      try {
        recognition.start();
      } catch (err: any) {
        console.warn("[VoiceAssistant] Failed to start recognition:", err);
        setIsListening(false);
        setError("Could not activate microphone. Spoken output is still available via 'Listen'.");
      }
    },
    [isSpeechRecognitionSupported, stopSpeaking, activeLang, options]
  );

  return {
    isListening,
    isProcessing,
    isSpeaking,
    isMuted,
    transcript,
    interimTranscript,
    error,
    voiceNotice,
    activeLanguage: activeLang,
    availableVoices,
    isSpeechRecognitionSupported,
    isSpeechSynthesisSupported,
    startListening,
    stopListening,
    speak,
    retrySpeak,
    stopSpeaking,
    toggleMute,
    clearError,
    clearNotice,
  };
}
