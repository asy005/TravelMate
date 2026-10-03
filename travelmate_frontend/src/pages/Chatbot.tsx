import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { MessageCircle, Send, Sparkles } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export default function Chatbot() {
  const { toast } = useToast();
  const [prompt, setPrompt] = useState("");
  const [reply, setReply] = useState("");
  const [loading, setLoading] = useState(false);

  const send = async () => {
    if (!prompt.trim() || loading) return;
    setLoading(true);
    setReply("");

    try {
      const res = await fetch("http://127.0.0.1:8000/chat/bot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      const j = await res.json();
      setReply(j.reply || j.error || "No response");
    } catch {
      toast({
        title: "Couldn't reach the assistant",
        description: "Please try again in a moment.",
        variant: "destructive",
      });
    }

    setLoading(false);
  };

  return (
    <div className="min-h-screen container mx-auto px-6 max-w-3xl pt-28 pb-16">
      <div className="flex items-center gap-2 mb-6">
        <MessageCircle className="h-6 w-6 text-coral" aria-hidden="true" />
        <h1 className="text-3xl font-bold">TravelMate AI Chat</h1>
      </div>

      <Card className="p-6 bg-card/95 backdrop-blur-md border border-white/20 animate-fade-up">
        <Label htmlFor="chat-prompt">Ask anything about your trip</Label>
        <Textarea
          id="chat-prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
          placeholder="e.g. What should I pack for a rainy trip to Goa?"
          className="mt-2"
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send();
          }}
        />
        <div className="mt-3 flex justify-end">
          <Button variant="hero" onClick={send} disabled={loading || !prompt.trim()}>
            <Send className="h-4 w-4 mr-2" />
            {loading ? "Sending..." : "Send"}
          </Button>
        </div>
      </Card>

      <Card className="mt-5 p-6 bg-card/70 backdrop-blur-md border border-white/10 min-h-[120px]">
        <p className="text-xs font-medium text-muted-foreground flex items-center gap-1 mb-2">
          <Sparkles className="h-3.5 w-3.5 text-coral" /> Reply
        </p>
        {loading ? (
          <p className="text-sm text-muted-foreground animate-pulse">Thinking...</p>
        ) : reply ? (
          <p className="text-sm leading-relaxed animate-fade-up">{reply}</p>
        ) : (
          <p className="text-sm text-muted-foreground">Your assistant's reply will appear here.</p>
        )}
      </Card>
    </div>
  );
}
