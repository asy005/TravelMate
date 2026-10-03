import { useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { KeyRound, Lock, CheckCircle2, AlertTriangle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

const ResetPassword = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const token = searchParams.get("token") || "";

  const [newPassword, setNewPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);

    try {
      const res = await fetch("http://127.0.0.1:8000/auth/password-reset/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: newPassword }),
      });

      const data = await res.json();

      if (!res.ok) {
        toast({
          title: "Couldn't reset your password",
          description: data.detail || "This reset link is invalid or has expired.",
          variant: "destructive",
        });
        setLoading(false);
        return;
      }

      setSuccess(true);
      setTimeout(() => navigate("/login"), 1500);
    } catch {
      toast({
        title: "Server error",
        description: "Please try again in a moment.",
        variant: "destructive",
      });
    }

    setLoading(false);
  };

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <Card className="w-full max-w-md p-8 bg-card/95 backdrop-blur-md border border-white/20 text-center animate-fade-up">
          <AlertTriangle className="h-8 w-8 text-amber-500 mx-auto mb-3" aria-hidden="true" />
          <p className="text-muted-foreground">
            This reset link is missing a token. Please request a new one.
          </p>
          <Button variant="outline" className="mt-4" onClick={() => navigate("/forgot-password")}>
            Request a new link
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6 py-24">
      <Card className="w-full max-w-md p-8 bg-card/95 backdrop-blur-md border border-white/20 shadow-xl animate-fade-up">
        <div className="flex flex-col items-center mb-6 text-center">
          <div className="h-12 w-12 rounded-full bg-primary/15 flex items-center justify-center mb-3">
            <KeyRound className="h-6 w-6 text-primary" aria-hidden="true" />
          </div>
          <h1 className="text-2xl font-bold">Set a new password</h1>
        </div>

        {success ? (
          <div className="flex flex-col items-center text-center py-4 animate-fade-up">
            <CheckCircle2 className="h-8 w-8 text-green-600 mb-3" aria-hidden="true" />
            <p className="text-sm">Password updated! Redirecting you to sign in...</p>
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
              <Label htmlFor="new_password">New password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
                <Input
                  id="new_password"
                  type="password"
                  autoComplete="new-password"
                  placeholder="••••••••"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="pl-9"
                  required
                />
              </div>
            </div>

            <Button type="submit" variant="hero" className="w-full h-11" disabled={loading || !newPassword.trim()}>
              {loading ? "Updating..." : "Update Password"}
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
};

export default ResetPassword;
