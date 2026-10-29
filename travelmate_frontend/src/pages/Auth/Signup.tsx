import { useState, useContext } from "react";
import { AuthContext } from "@/hooks/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { User, Mail, Lock, UserPlus, AlertCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

const Signup = () => {
  const { login } = useContext(AuthContext);
  const { toast } = useToast();

  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
    setError("");
  };

  const handleSignup = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (loading) return;

    setLoading(true);
    setError("");

    try {
      const res = await fetch("http://127.0.0.1:8000/auth/signup", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        const message =
          typeof data.detail === "string"
            ? data.detail
            : Array.isArray(data.detail) && data.detail.length > 0
            ? data.detail.map((d: any) => d.msg || d).join(", ")
            : "Unable to create your account. Please try again.";

        setError(message);

        toast({
          title: "Sign up failed",
          description: message,
          variant: "destructive",
        });

        return;
      }

      // Supports either an object response or a raw string token.
      const token =
        typeof data === "string" ? data : data.token;

      const refreshToken =
        typeof data === "object" && data !== null
          ? data.refresh_token
          : undefined;

      if (!token) {
        setError(
          "Your account was created, but automatic sign-in could not be completed. Please sign in."
        );

        toast({
          title: "Account created",
          description: "Please sign in to continue.",
        });

        window.location.href = "/login";
        return;
      }

      login(token, refreshToken);
      window.location.href = "/";
    } catch {
      const message =
        "Unable to connect to the server. Please try again.";

      setError(message);

      toast({
        title: "Connection error",
        description: message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-6 py-24">
      <Card className="w-full max-w-md p-8 bg-card/95 backdrop-blur-md border border-white/20 shadow-xl animate-fade-up">
        <div className="flex flex-col items-center mb-6">
          <div className="h-12 w-12 rounded-full bg-primary/15 flex items-center justify-center mb-3">
            <UserPlus
              className="h-6 w-6 text-primary"
              aria-hidden="true"
            />
          </div>

          <h1 className="text-2xl font-bold">
            Create your account
          </h1>

          <p className="text-sm text-muted-foreground mt-1">
            Start planning smarter trips with AI
          </p>
        </div>

        {error && (
          <div
            role="alert"
            aria-live="polite"
            className="mb-5 flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive"
          >
            <AlertCircle
              className="h-5 w-5 shrink-0"
              aria-hidden="true"
            />
            <span>{error}</span>
          </div>
        )}

        <form className="space-y-4" onSubmit={handleSignup}>
          <div>
            <Label htmlFor="username">Username</Label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="username"
                name="username"
                autoComplete="username"
                placeholder="Your name"
                value={form.username}
                onChange={handleChange}
                className="pl-9"
                required
              />
            </div>
          </div>

          <div>
            <Label htmlFor="email">Email</Label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={form.email}
                onChange={handleChange}
                className="pl-9"
                required
              />
            </div>
          </div>

          <div>
            <Label htmlFor="password">Password</Label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="new-password"
                placeholder="Enter your password"
                value={form.password}
                onChange={handleChange}
                className="pl-9"
                required
              />
            </div>
          </div>

          <Button
            type="submit"
            variant="hero"
            className="w-full h-11"
            disabled={loading}
          >
            {loading ? "Creating account..." : "Sign Up"}
          </Button>
        </form>

        <p className="text-center mt-5 text-sm text-muted-foreground">
          Already have an account?{" "}
          <a
            href="/login"
            className="underline hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
          >
            Sign in
          </a>
        </p>
      </Card>
    </div>
  );
};

export default Signup;