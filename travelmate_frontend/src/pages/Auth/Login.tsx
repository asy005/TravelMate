import { useState, useContext } from "react";
import { AuthContext } from "@/hooks/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Mail, Lock, LogIn } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

const Login = () => {
  const { login } = useContext(AuthContext);
  const { toast } = useToast();

  const [form, setForm] = useState({ email: "", password: "" });
  const [loading, setLoading] = useState(false);

  const handleChange = (e: any) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleLogin = async () => {
    setLoading(true);

    try {
      const res = await fetch("http://127.0.0.1:8000/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      const data = await res.json();

      if (!res.ok) {
        toast({
          title: "Couldn't sign in",
          description: data.detail || "Invalid email or password.",
          variant: "destructive",
        });
        setLoading(false);
        return;
      }

      login(data.token, data.refresh_token);
      window.location.href = "/";
    } catch {
      toast({
        title: "Server error",
        description: "Please try again in a moment.",
        variant: "destructive",
      });
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-6 py-24">
      <Card className="w-full max-w-md p-8 bg-card/95 backdrop-blur-md border border-white/20 shadow-xl animate-fade-up">
        <div className="flex flex-col items-center mb-6">
          <div className="h-12 w-12 rounded-full bg-primary/15 flex items-center justify-center mb-3">
            <LogIn className="h-6 w-6 text-primary" aria-hidden="true" />
          </div>
          <h1 className="text-2xl font-bold">Welcome back</h1>
          <p className="text-sm text-muted-foreground mt-1">Sign in to continue planning your trip</p>
        </div>

        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            handleLogin();
          }}
        >
          <div>
            <Label htmlFor="email">Email</Label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
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
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                value={form.password}
                onChange={handleChange}
                className="pl-9"
                required
              />
            </div>
          </div>

          <Button type="submit" variant="hero" className="w-full h-11" disabled={loading}>
            {loading ? "Signing in..." : "Sign In"}
          </Button>
        </form>

        <p className="text-center mt-5 text-sm text-muted-foreground">
          <a href="/forgot-password" className="underline hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded">
            Forgot your password?
          </a>
        </p>
        <p className="text-center mt-2 text-sm text-muted-foreground">
          New to TravelMate?{" "}
          <a href="/signup" className="underline hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded">
            Create an account
          </a>
        </p>
      </Card>
    </div>
  );
};

export default Login;
