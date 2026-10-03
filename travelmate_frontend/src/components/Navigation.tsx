import { Link } from "react-router-dom";
import { useState, useContext } from "react";
import { Menu, X, MapPin } from "lucide-react";
import { AuthContext } from "@/hooks/AuthContext";
import { Button } from "@/components/ui/button";

const NAV_LINKS = [
  { to: "/", label: "Home" },
  { to: "/favorites", label: "Favorites" },
  { to: "/chat", label: "Chat" },
  { to: "/partner/dashboard", label: "Partner Portal" },
];

export const Navigation = () => {
  const [open, setOpen] = useState(false);
  const { token, logout } = useContext(AuthContext);

  return (
    <nav className="w-full bg-white/70 backdrop-blur-xl border-b border-white/20 shadow-sm fixed top-0 left-0 z-50">
      <div className="container mx-auto px-6 py-4 flex items-center justify-between">
        {/* LOGO */}
        <Link
          to="/"
          className="flex items-center gap-2 text-2xl font-bold text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
        >
          <MapPin className="h-6 w-6" aria-hidden="true" />
          TravelMate
        </Link>

        {/* DESKTOP MENU */}
        <div className="hidden md:flex items-center gap-8">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className="text-foreground hover:text-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
            >
              {link.label}
            </Link>
          ))}

          {/* AUTH BUTTONS */}
          {token ? (
            <Button variant="destructive" size="sm" onClick={logout}>
              Logout
            </Button>
          ) : (
            <div className="flex items-center gap-3">
              <Button variant="outline" size="sm" asChild>
                <Link to="/login">Sign In</Link>
              </Button>
              <Button variant="hero" size="sm" asChild>
                <Link to="/signup">Sign Up</Link>
              </Button>
            </div>
          )}
        </div>

        {/* MOBILE MENU BUTTON */}
        <button
          className="md:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          aria-controls="mobile-nav-menu"
          aria-label={open ? "Close menu" : "Open menu"}
        >
          {open ? <X className="h-6 w-6" aria-hidden="true" /> : <Menu className="h-6 w-6" aria-hidden="true" />}
        </button>
      </div>

      {/* MOBILE MENU */}
      {open && (
        <div
          id="mobile-nav-menu"
          className="md:hidden bg-white/90 backdrop-blur-xl border-t border-white/20 px-6 py-4 space-y-4 animate-fade-up"
        >
          {NAV_LINKS.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className="block text-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
              onClick={() => setOpen(false)}
            >
              {link.label}
            </Link>
          ))}

          {token ? (
            <Button
              variant="destructive"
              className="w-full"
              onClick={() => {
                logout();
                setOpen(false);
              }}
            >
              Logout
            </Button>
          ) : (
            <div className="flex flex-col gap-3">
              <Button variant="outline" className="w-full" asChild>
                <Link to="/login" onClick={() => setOpen(false)}>Sign In</Link>
              </Button>
              <Button variant="hero" className="w-full" asChild>
                <Link to="/signup" onClick={() => setOpen(false)}>Sign Up</Link>
              </Button>
            </div>
          )}
        </div>
      )}
    </nav>
  );
};
