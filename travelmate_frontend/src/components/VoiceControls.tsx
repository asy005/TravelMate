import { Button } from "@/components/ui/button";
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Square,
  AlertCircle,
  Info,
  Loader2,
  X,
} from "lucide-react";
import { VoiceAssistantState } from "@/hooks/useVoiceAssistant";

interface VoiceControlsProps {
  voice: VoiceAssistantState;
  disabled?: boolean;
  className?: string;
  showMuteToggle?: boolean;
}

export const VoiceInputButton = ({
  voice,
  disabled = false,
}: {
  voice: VoiceAssistantState;
  disabled?: boolean;
}) => {
  const {
    isListening,
    isProcessing,
    isSpeechRecognitionSupported,
    startListening,
    stopListening,
  } = voice;

  const handleClick = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  const title = !isSpeechRecognitionSupported
    ? "Voice input not supported in this browser (Audio playback remains available)"
    : isListening
    ? "Listening... click to stop"
    : "Click to speak with TravelMate";

  return (
    <Button
      type="button"
      variant={isListening ? "destructive" : "outline"}
      size="icon"
      onClick={handleClick}
      disabled={disabled || isProcessing}
      title={title}
      aria-label={title}
      className={`relative h-12 w-12 rounded-xl shrink-0 transition-all ${
        isListening ? "animate-pulse ring-2 ring-destructive ring-offset-2" : ""
      }`}
    >
      {isProcessing ? (
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
      ) : isListening ? (
        <Mic className="h-5 w-5 text-white animate-bounce" />
      ) : isSpeechRecognitionSupported ? (
        <Mic className="h-5 w-5 text-coral" />
      ) : (
        <MicOff className="h-5 w-5 text-muted-foreground" />
      )}
    </Button>
  );
};

export const VoiceStatusBanner = ({ voice }: { voice: VoiceAssistantState }) => {
  const {
    isListening,
    isProcessing,
    isSpeaking,
    interimTranscript,
    error,
    voiceNotice,
    clearError,
    clearNotice,
  } = voice;

  return (
    <div className="space-y-2">
      {/* Playback or microphone error notification */}
      {error && (
        <div
          role="alert"
          className="flex items-center justify-between gap-2 p-3 text-xs bg-destructive/10 text-destructive border border-destructive/20 rounded-xl mb-3 animate-fade-up"
        >
          <div className="flex items-center gap-2 flex-wrap">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
            {voice.retrySpeak && error.toLowerCase().includes("playback") && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={voice.retrySpeak}
                className="h-6 px-2 text-xs border-destructive/30 hover:bg-destructive/20 text-destructive font-medium"
              >
                Retry audio
              </Button>
            )}
          </div>
          <button
            onClick={clearError}
            className="text-destructive hover:opacity-80 p-1 shrink-0"
            aria-label="Dismiss error"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Voice language availability notice (e.g. Tamil / Kannada fallback notification) */}
      {voiceNotice && (
        <div
          role="status"
          className="flex items-center justify-between gap-2 p-2.5 text-xs bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20 rounded-xl mb-3 animate-fade-up"
        >
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 shrink-0 text-amber-600" />
            <span>{voiceNotice}</span>
          </div>
          <button
            onClick={clearNotice}
            className="hover:opacity-80 p-1"
            aria-label="Dismiss voice notice"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Spoken playback active banner */}
      {isSpeaking && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center justify-between gap-2 p-2.5 bg-primary/10 border border-primary/20 rounded-xl mb-3 text-xs text-primary font-medium animate-pulse"
        >
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-primary animate-ping" />
            <span>Speaking response... (Click "Stop" or listen)</span>
          </div>
          <button
            onClick={voice.stopSpeaking}
            className="text-destructive hover:underline text-xs flex items-center gap-1 font-semibold"
            aria-label="Stop playback"
          >
            <Square className="h-3 w-3 fill-current" /> Stop
          </button>
        </div>
      )}

      {/* Microphone listening banner */}
      {isListening && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-2 p-2.5 bg-coral/10 border border-coral/30 rounded-xl mb-3 text-xs text-coral font-medium animate-pulse"
        >
          <span className="h-2 w-2 rounded-full bg-coral animate-ping" />
          <span>Listening... {interimTranscript ? `"${interimTranscript}"` : "speak your travel query now"}</span>
        </div>
      )}

      {/* Transcribing speech banner */}
      {isProcessing && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-2 p-2.5 bg-sky/10 border border-sky/30 rounded-xl mb-3 text-xs text-sky font-medium"
        >
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          <span>Transcribing speech into conversation...</span>
        </div>
      )}
    </div>
  );
};

export const SpeechPlaybackControls = ({
  voice,
  textToSpeak,
  lang,
}: {
  voice: VoiceAssistantState;
  textToSpeak: string;
  lang?: string;
}) => {
  const { isSpeaking, isMuted, isSpeechSynthesisSupported, speak, stopSpeaking, toggleMute } = voice;

  if (!isSpeechSynthesisSupported || !textToSpeak) {
    return null;
  }

  const targetLang = lang || voice.activeLanguage;

  return (
    <div className="inline-flex items-center gap-2 mt-1 text-xs text-muted-foreground flex-wrap">
      {isSpeaking ? (
        <Button
          variant="outline"
          size="sm"
          onClick={stopSpeaking}
          className="h-7 px-2.5 text-xs text-destructive hover:bg-destructive/10 border-destructive/30"
          title="Stop reading aloud"
          aria-label="Stop reading aloud"
        >
          <Square className="h-3 w-3 mr-1 fill-current" /> Stop
        </Button>
      ) : (
        <Button
          variant="outline"
          size="sm"
          onClick={() => speak(textToSpeak, targetLang, { force: true })}
          className="h-7 px-2.5 text-xs text-primary hover:bg-primary/10 border-primary/30 font-medium"
          title="Listen to response"
          aria-label="Listen to response"
        >
          <Volume2 className="h-3.5 w-3.5 mr-1" /> Listen
        </Button>
      )}

      <Button
        variant="ghost"
        size="sm"
        onClick={toggleMute}
        className="h-7 px-2 text-xs text-muted-foreground hover:bg-muted"
        title={isMuted ? "Turn on automatic speech for assistant replies" : "Turn off automatic speech"}
        aria-label={isMuted ? "Turn on auto-speech" : "Turn off auto-speech"}
      >
        {isMuted ? (
          <>
            <VolumeX className="h-3 w-3 text-muted-foreground mr-1" />
            <span className="text-[11px]">Auto-speech off</span>
          </>
        ) : (
          <>
            <Volume2 className="h-3 w-3 text-coral mr-1" />
            <span className="text-[11px]">Auto-speech on</span>
          </>
        )}
      </Button>
    </div>
  );
};
