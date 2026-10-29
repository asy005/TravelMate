import { createContext, useState, useEffect } from "react";

export const AuthContext = createContext({
  token: null as string | null,
  role: null as string | null,
  login: (token: string, refreshToken?: string, role?: string, email?: string, username?: string) => {},
  logout: () => {},
});

export const AuthProvider = ({ children }: any) => {
  const [token, setToken] = useState<string | null>(() => {
    return localStorage.getItem("travelmate_token");
  });
  const [role, setRole] = useState<string | null>(() => {
    return localStorage.getItem("travelmate_role");
  });

  useEffect(() => {
    const stored = localStorage.getItem("travelmate_token");
    if (stored !== token) setToken(stored);
    const storedRole = localStorage.getItem("travelmate_role");
    if (storedRole !== role) setRole(storedRole);
  }, [token, role]);

  const login = (
    newToken: string,
    refreshToken?: string,
    userRole?: string,
    email?: string,
    username?: string
  ) => {
    localStorage.setItem("travelmate_token", newToken);
    if (refreshToken) {
      localStorage.setItem("travelmate_refresh_token", refreshToken);
    }
    if (userRole) {
      localStorage.setItem("travelmate_role", userRole);
      setRole(userRole);
    }
    if (email) {
      localStorage.setItem("travelmate_email", email);
    }
    if (username) {
      localStorage.setItem("travelmate_username", username);
    }
    setToken(newToken);
  };

  const logout = () => {
    const refreshToken = localStorage.getItem("travelmate_refresh_token");

    // Best-effort server-side revocation -- logout should still succeed
    // locally even if this request fails (e.g. offline).
    if (refreshToken) {
      fetch("http://127.0.0.1:8000/auth/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      }).catch(() => {});
    }

    localStorage.removeItem("travelmate_token");
    localStorage.removeItem("travelmate_refresh_token");
    localStorage.removeItem("travelmate_role");
    localStorage.removeItem("travelmate_email");
    localStorage.removeItem("travelmate_username");
    setToken(null);
    setRole(null);
    window.location.href = "/";
  };

  return (
    <AuthContext.Provider value={{ token, role, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

/**
 * Exchanges the stored refresh token for a new access token. Returns the
 * new access token, or null if the refresh token is missing/invalid (in
 * which case the caller should treat the user as logged out).
 */
export async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem("travelmate_refresh_token");
  if (!refreshToken) return null;

  try {
    const res = await fetch("http://127.0.0.1:8000/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) {
      localStorage.removeItem("travelmate_token");
      localStorage.removeItem("travelmate_refresh_token");
      localStorage.removeItem("travelmate_role");
      return null;
    }

    const data = await res.json();
    const newAccessToken = data.token || data.access_token;
    if (newAccessToken) {
      localStorage.setItem("travelmate_token", newAccessToken);
      return newAccessToken;
    }
    return null;
  } catch {
    return null;
  }
}
