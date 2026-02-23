"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import {
  authAPI,
  AuthUser,
  setToken,
  clearToken,
  getCurrentAdvertiserId,
  setCurrentAdvertiserId,
  clearCurrentAdvertiserId,
} from "./api";
import { invalidateAllCache } from "./use-api";

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  currentAdvertiserId: number | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
  switchAdvertiser: (id: number) => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentAdvertiserId, setCurrentAdvId] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const me = await authAPI.me();
      setUser(me);
      // Initialize advertiser ID if not set or invalid
      const stored = getCurrentAdvertiserId();
      const advIds = (me.advertisers || []).map((a) => a.id);
      if (stored && advIds.includes(Number(stored))) {
        setCurrentAdvId(Number(stored));
      } else if (advIds.length > 0) {
        setCurrentAdvertiserId(advIds[0]);
        setCurrentAdvId(advIds[0]);
      }
    } catch {
      clearToken();
      clearCurrentAdvertiserId();
      setUser(null);
      setCurrentAdvId(null);
    }
  }, []);

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
    if (token) {
      refresh().finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [refresh]);

  // Listen for 401 from any API call mid-session → auto-logout
  useEffect(() => {
    function handleExpired() {
      clearToken();
      clearCurrentAdvertiserId();
      setUser(null);
      setCurrentAdvId(null);
    }
    window.addEventListener("auth:expired", handleExpired);
    return () => window.removeEventListener("auth:expired", handleExpired);
  }, []);

  async function login(email: string, password: string) {
    const res = await authAPI.login(email, password);
    setToken(res.token);
    setUser(res.user);
    const advs = res.user.advertisers || [];
    if (advs.length > 0) {
      setCurrentAdvertiserId(advs[0].id);
      setCurrentAdvId(advs[0].id);
    }
  }

  async function register(email: string, password: string, name?: string) {
    const res = await authAPI.register(email, password, name);
    setToken(res.token);
    setUser(res.user);
  }

  function logout() {
    clearToken();
    clearCurrentAdvertiserId();
    setUser(null);
    setCurrentAdvId(null);
  }

  function switchAdvertiser(id: number) {
    setCurrentAdvertiserId(id);
    setCurrentAdvId(id);
    // Invalidate SWR cache so all pages refetch with new advertiser
    invalidateAllCache();
  }

  return (
    <AuthContext.Provider value={{ user, loading, currentAdvertiserId, login, register, logout, refresh, switchAdvertiser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
