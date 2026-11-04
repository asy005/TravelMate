import { useState, useContext } from "react";
import { useLocation, useSearchParams, Link } from "react-router-dom";
import { AuthContext } from "@/hooks/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Mail, Lock, LogIn, Building2, AlertCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { loginUser, extractErrorMessage } from "@/lib/api";

interface LoginProps {
  isPartner?: boolean;
}

const Login = ({ isPartner: propIsPartner }: LoginProps) => {
  const { login } = useContext(AuthContext);
  const { toast } = useToast();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  // Role detection: prop, path (/partner/login), or query param (?role=partner)
  const isPartner =
    propIsPartner ||
    location.pathname.startsWith("/partner") ||
    searchParams.get("role") === "partner";

  const redirectParam = searchParams.get("redirect");

  const [form, setForm] = useState({ email: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
    if (errorMessage) setErrorMessage(null);
  };

  const handleLogin = async () => {
    setLoading(true);
    setErrorMessage(null);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 12000);

    try {
      const data = await loginUser(form, controller.signal);

      const token = data.token || data.access_token;
      const refreshToken = data.refresh_token || data.refreshToken;
      if (!token) {
        setErrorMessage("Authentication succeeded but no access token was returned. Please try again.");
        return;
      }

      // Store tokens and user profile securely in localStorage & Context
      login(
        token,
        refreshToken,
        data.role,
        data.email,
        data.username
      );

      toast({
        title: "Signed in successfully",
        description: isPartner ? "Redirecting to your Partner Portal..." : "Welcome back!",
      });

      // Role-aware redirection
      if (isPartner) {
        if (data.role === "partner") {
          window.location.href = redirectParam || "/partner/dashboard";
        } else {
          // User logged into partner portal with standard traveller account
          toast({
            title: "Partner registration needed",
            description: "Please complete your business registration to access the partner dashboard.",
          });
          window.location.href = "/partner/register";
        }
      } else {
        if (redirectParam) {
          if (redirectParam.startsWith("/partner") && data.role !== "partner") {
            window.location.href = "/partner/register";
          } else {
            window.location.href = redirectParam;
          }
        } else if (data.role === "partner") {
          // Partner signing in from generic login
          window.location.href = "/partner/dashboard";
        } else {
          window.location.href = "/";
        }
      }
    } catch (err: any) {
      let desc = err?.message || "Unable to connect to the server. Please check your network connection.";
      if (err?.name === "AbortError") {
        desc = "Connection timed out. Please check that the backend server is running.";
      }
      setErrorMessage(desc);
      toast({
        title: "Sign in failed",
        description: desc,
        variant: "destructive",
      });
    } finally {
      clearTimeout(timeoutId);
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-6 py-24">
      <Card className="w-full max-w-md p-8 bg-card/95 backdrop-blur-md border border-white/20 shadow-xl animate-fade-up">
        {/* Header Branding */}
        <div className="flex flex-col items-center mb-6 text-center">
          <div
            className={`h-12 w-12 rounded-full flex items-center justify-center mb-3 ${
              isPartner
                ? "bg-amber-500/15 text-amber-600 dark:text-amber-400 ring-2 ring-amber-500/20"
                : "bg-primary/15 text-primary"
            }`}
          >
            {isPartner ? (
              <Building2 className="h-6 w-6" aria-hidden="true" />
            ) : (
              <LogIn className="h-6 w-6" aria-hidden="true" />
            )}
          </div>
          <h1 className="text-2xl font-bold tracking-tight">
            {isPartner ? "Welcome back, Travel Partner" : "Welcome back"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {isPartner
              ? "Manage your listings and grow your travel business"
              : "Sign in to continue planning your trip"}
          </p>
        </div>

        {/* Inline Error Notification */}
        {errorMessage && (
          <div
            role="alert"
            className="flex items-start gap-2.5 p-3 mb-4 text-xs bg-destructive/10 text-destructive border border-destructive/20 rounded-xl animate-fade-up"
          >
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span className="leading-relaxed">{errorMessage}</span>
          </div>
        )}

        {/* Login Form */}
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            handleLogin();
          }}
        >
          <div>
            <Label htmlFor="email">{isPartner ? "Business Email" : "Email"}</Label>
            <div className="relative mt-1">
              <Mail
                className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"
                aria-hidden="true"
              />
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                placeholder={isPartner ? "partner@company.com" : "you@example.com"}
                value={form.email}
                onChange={handleChange}
                className="pl-9"
                required
              />
            </div>
          </div>

          <div>
            <Label htmlFor="password">Password</Label>
            <div className="relative mt-1">
              <Lock
                className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"
                aria-hidden="true"
              />
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

          <Button
            type="submit"
            variant="hero"
            className={`w-full h-11 ${
              isPartner
                ? "bg-gradient-to-r from-amber-600 to-amber-700 hover:from-amber-700 hover:to-amber-800 text-white"
                : ""
            }`}
            disabled={loading}
          >
            {loading ? "Signing in..." : isPartner ? "Sign In to Partner Portal" : "Sign In"}
          </Button>
        </form>

        {/* Alternative Links & Role Switching */}
        <div className="mt-6 pt-5 border-t border-white/10 space-y-2.5 text-center text-xs text-muted-foreground">
          <p>
            <Link
              to="/forgot-password"
              className="underline hover:text-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
            >
              Forgot your password?
            </Link>
          </p>

          {isPartner ? (
            <>
              <p>
                New partner?{" "}
                <Link
                  to="/partner/register"
                  className="font-medium text-foreground underline hover:text-primary transition-colors"
                >
                  Register your business
                </Link>
              </p>
              <p className="pt-2">
                Looking for traveller sign-in?{" "}
                <Link
                  to="/login"
                  className="text-primary underline hover:opacity-80 transition-opacity"
                >
                  Traveller login
                </Link>
              </p>
            </>
          ) : (
            <>
              <p>
                New to TravelMate?{" "}
                <Link
                  to="/signup"
                  className="font-medium text-foreground underline hover:text-primary transition-colors"
                >
                  Create an account
                </Link>
              </p>
              <p className="pt-2">
                Are you a travel business partner?{" "}
                <Link
                  to="/partner/login"
                  className="text-primary underline hover:opacity-80 transition-opacity"
                >
                  Partner Portal login
                </Link>
              </p>
            </>
          )}
        </div>
      </Card>
    </div>
  );
};

export default Login;
