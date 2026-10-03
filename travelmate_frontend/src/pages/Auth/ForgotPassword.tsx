import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { KeyRound, Mail, CheckCircle2 } from "lucide-react";

const ForgotPassword = () => {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);

    try {
      await fetch("http://127.0.0.1:8000/auth/password-reset/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
    } catch {
      // Intentionally still shown as "sent" -- the endpoint never reveals
      // whether an email is registered, so there's nothing account-specific
      // to surface here either way.
    }

    setSent(true);
    setLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-6 py-24">
      <Card className="w-full max-w-md p-8 bg-card/95 backdrop-blur-md border border-white/20 shadow-xl animate-fade-up">
        <div className="flex flex-col items-center mb-6 text-center">
          <div className="h-12 w-12 rounded-full bg-primary/15 flex items-center justify-center mb-3">
            <KeyRound className="h-6 w-6 text-primary" aria-hidden="true" />
          </div>
          <h1 className="text-2xl font-bold">Reset your password</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Enter your email and we'll send you a link to reset it.
          </p>
        </div>

        {sent ? (
          <div className="flex flex-col items-center text-center py-4 animate-fade-up">
            <CheckCircle2 className="h-8 w-8 text-green-600 mb-3" aria-hidden="true" />
            <p className="text-sm">
              If <span className="font-medium">{email}</span> is registered, a reset link is on its way.
            </p>
          </div>
        ) : (
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              handleSubmit();
            }}
          >
            <div>
              <Label htmlFor="email">Email</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-9"
                  required
                />
              </div>
            </div>

            <Button type="submit" variant="hero" className="w-full h-11" disabled={loading || !email.trim()}>
              {loading ? "Sending..." : "Send Reset Link"}
            </Button>
          </form>
        )}

        <p className="text-center mt-5 text-sm text-muted-foreground">
          <a href="/login" className="underline hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded">
            Back to sign in
          </a>
        </p>
      </Card>
    </div>
  );
};

export default ForgotPassword;
