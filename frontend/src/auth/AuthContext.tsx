import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, refreshSession, setAccessToken, setSessionLostHandler } from "../api/client";
import type { TokenOut, User } from "../api/types";

interface AuthState {
  user: User | null; loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (u: User) => void;
}
const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setSessionLostHandler(() => setUser(null));
    let alive = true;
    (async () => {
      // Restore a session from the httpOnly refresh cookie, if one exists.
      if (await refreshSession()) {
        try { const me = await api.get<User>("/users/me"); if (alive) setUser(me); } catch { /* ignore */ }
      }
      if (alive) setLoading(false);
    })();
    return () => { alive = false; setSessionLostHandler(null); };
  }, []);

  const adopt = (t: TokenOut) => { setAccessToken(t.access_token); setUser(t.user); };
  const login = useCallback(async (email: string, password: string) => {
    adopt(await api.post<TokenOut>("/auth/login", { email, password }));
  }, []);
  const register = useCallback(async (email: string, password: string, name: string) => {
    adopt(await api.post<TokenOut>("/auth/register", { email, password, name }));
  }, []);
  const logout = useCallback(async () => {
    try { await api.post("/auth/logout"); } catch { /* session may already be gone */ }
    setAccessToken(null); setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, login, register, logout, setUser }), [user, loading, login, register, logout]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside AuthProvider");
  return v;
}
