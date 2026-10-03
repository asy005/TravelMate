import { createContext, useState, useEffect } from "react";

export const AuthContext = createContext({
  token: null as string | null,
  login: (token: string, refreshToken?: string) => {},
  logout: () => {},
});

export const AuthProvider = ({ children }: any) => {
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("travelmate_token");
    if (stored) setToken(stored);
  }, []);

  const login = (token: string, refreshToken?: string) => {
    localStorage.setItem("travelmate_token", token);
    if (refreshToken) {
      localStorage.setItem("travelmate_refresh_token", refreshToken);
    }
    setToken(token);
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
    setToken(null);
    window.location.href = "/";
  };

  return (
    <AuthContext.Provider value={{ token, login, logout }}>
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

    if (!res.ok) return null;

    const data = await res.json();
    localStorage.setItem("travelmate_token", data.token);
    return data.token;
  } catch {
    return null;
  }
}
