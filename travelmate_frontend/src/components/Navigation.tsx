import { Link, useNavigate, useLocation } from "react-router-dom";
import { useState, useContext } from "react";
import { Menu, MapPin, Home, Heart, Building2, LogIn, LogOut, UserPlus, X } from "lucide-react";
import { AuthContext } from "@/hooks/AuthContext";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

const BASE_NAV_LINKS = [
  { to: "/", label: "Home", icon: Home },
  { to: "/favorites", label: "Favorites", icon: Heart },
];

const PARTNER_NAV_LINK = {
  to: "/partner/dashboard",
  label: "Partner Portal",
  icon: Building2,
};

export const Navigation = () => {
  const [open, setOpen] = useState(false);
  const { token, role, logout } = useContext(AuthContext);
  const location = useLocation();
  const navigate = useNavigate();

  const isPartnerAuthenticated = Boolean(token && role === "partner");
  const navLinks = isPartnerAuthenticated
    ? [...BASE_NAV_LINKS, PARTNER_NAV_LINK]
    : BASE_NAV_LINKS;

  const close = () => setOpen(false);

  const handleLogout = () => {
    logout();
    close();
  };

  const isActive = (to: string) =>
    to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);

  return (
    <>
      {/* ── Top bar ───────────────────────────────────────────────────────── */}
      <nav
        className="w-full bg-white/70 backdrop-blur-xl border-b border-white/20 shadow-sm fixed top-0 left-0 z-50"
        aria-label="Main navigation"
      >
        <div className="container mx-auto px-6 py-4 flex items-center justify-between">
          {/* Logo */}
          <Link
            to="/"
            className="flex items-center gap-2 text-2xl font-bold text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
          >
            <MapPin className="h-6 w-6" aria-hidden="true" />
            TravelMate
          </Link>

          {/* Desktop links */}
          <div className="hidden md:flex items-center gap-8">
            {navLinks.map(({ to, label }) => (
              <Link
                key={to}
                to={to}
                className={`text-sm font-medium transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded ${
                  isActive(to) ? "text-primary" : "text-foreground"
                }`}
              >
                {label}
              </Link>
            ))}

            {token ? (
              <Button variant="destructive" size="sm" onClick={handleLogout}>
                <LogOut className="h-4 w-4 mr-1" />
                Logout
              </Button>
            ) : (
              <div className="flex items-center gap-3">
                <Button variant="outline" size="sm" asChild>
                  <Link to="/login">
                    <LogIn className="h-4 w-4 mr-1" />
                    Sign In
                  </Link>
                </Button>
                <Button variant="hero" size="sm" asChild>
                  <Link to="/signup">
                    <UserPlus className="h-4 w-4 mr-1" />
                    Sign Up
                  </Link>
                </Button>
              </div>
            )}
          </div>

          {/* Mobile hamburger */}
          <button
            className="md:hidden p-2 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => setOpen(true)}
            aria-label="Open navigation menu"
            aria-expanded={open}
            aria-controls="sidebar-nav"
          >
            <Menu className="h-6 w-6" aria-hidden="true" />
          </button>
        </div>
      </nav>

      {/* ── Sidebar drawer (mobile + accessible overlay) ──────────────────── */}
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent
          side="left"
          id="sidebar-nav"
          className="w-72 flex flex-col pt-6 bg-background/95 backdrop-blur-xl"
          aria-label="Navigation drawer"
        >
          <SheetHeader className="mb-6 text-left">
            <SheetTitle className="flex items-center gap-2 text-primary">
              <MapPin className="h-5 w-5" />
              TravelMate
            </SheetTitle>
          </SheetHeader>

          <nav className="flex flex-col gap-1 flex-1">
            {navLinks.map(({ to, label, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                onClick={close}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-colors ${
                  isActive(to)
                    ? "bg-primary/10 text-primary"
                    : "hover:bg-muted text-foreground"
                }`}
              >
                <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                {label}
              </Link>
            ))}
          </nav>

          {/* Auth section at bottom of drawer */}
          <div className="border-t border-white/10 pt-4 mt-2 flex flex-col gap-2">
            {token ? (
              <Button
                variant="destructive"
                className="w-full"
                onClick={handleLogout}
              >
                <LogOut className="h-4 w-4 mr-2" />
                Logout
              </Button>
            ) : (
              <>
                <Button variant="outline" className="w-full" asChild>
                  <Link to="/login" onClick={close}>
                    <LogIn className="h-4 w-4 mr-2" />
                    Sign In
                  </Link>
                </Button>
                <Button variant="hero" className="w-full" asChild>
                  <Link to="/signup" onClick={close}>
                    <UserPlus className="h-4 w-4 mr-2" />
                    Sign Up
                  </Link>
                </Button>
                <div className="pt-2 text-center text-xs text-muted-foreground border-t border-white/10 mt-1">
                  <Link
                    to="/partner/login"
                    onClick={close}
                    className="hover:text-primary transition-colors inline-flex items-center gap-1.5 py-1 text-muted-foreground"
                  >
                    <Building2 className="h-3.5 w-3.5" />
                    Partner Portal Sign In
                  </Link>
                </div>
              </>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
};
