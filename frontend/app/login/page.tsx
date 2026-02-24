"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { exchangeMobsuccessAuth } from "@/lib/api";
import { Sparkles, AlertCircle, LogIn } from "lucide-react";

const MS_REMOTE_AUTH_URL = (process.env.NEXT_PUBLIC_MS_REMOTE_AUTH_URL || "https://app.mobsuccess.com/auth").trim();

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { loginWithToken } = useAuth();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const userId = searchParams.get("userId");
  const authId = searchParams.get("authId");

  useEffect(() => {
    if (!userId || !authId) return;

    let cancelled = false;

    async function handleSSOCallback() {
      setLoading(true);
      setError("");
      try {
        const token = await exchangeMobsuccessAuth(userId!, authId!);
        if (cancelled) return;
        await loginWithToken(token);
        if (cancelled) return;
        // Clean URL params before navigating
        window.history.replaceState({}, "", "/login");
        router.replace("/");
      } catch (err: any) {
        if (cancelled) return;
        setError(err.message || "Erreur lors de la connexion SSO");
        setLoading(false);
      }
    }

    handleSSOCallback();
    return () => { cancelled = true; };
  }, [userId, authId, loginWithToken, router]);

  function handleLogin() {
    const returnUrl = `${window.location.origin}/login`;
    window.location.href = `${MS_REMOTE_AUTH_URL}?to=${encodeURIComponent(returnUrl)}`;
  }

  // SSO callback in progress
  if (userId && authId && loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-white to-violet-50/30">
        <div className="text-center space-y-4">
          <div className="flex items-center justify-center">
            <div className="h-10 w-10 rounded-full border-4 border-violet-200 border-t-violet-600 animate-spin" />
          </div>
          <p className="text-sm text-muted-foreground font-medium">Connexion en cours...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-white to-violet-50/30">
      <div className="w-full max-w-sm mx-4">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-600 to-indigo-600 shadow-lg shadow-violet-200/50">
              <Sparkles className="h-6 w-6 text-white" />
            </div>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">
            panoram<span className="bg-gradient-to-r from-violet-600 to-indigo-500 bg-clip-text text-transparent">AI</span>
          </h1>
          <p className="text-[11px] text-muted-foreground">
            by <span className="font-semibold">mobsuccess</span>
          </p>
          <p className="text-muted-foreground text-sm mt-2">
            Connectez-vous avec votre compte Mobsuccess
          </p>
        </div>

        {/* SSO Button */}
        <div className="rounded-2xl border bg-card p-6 space-y-4 shadow-sm">
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          <button
            onClick={handleLogin}
            className="w-full h-11 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 text-white text-sm font-semibold shadow-sm hover:from-violet-700 hover:to-indigo-700 transition-all flex items-center justify-center gap-2"
          >
            <LogIn className="h-4 w-4" />
            Se connecter avec Mobsuccess
          </button>
        </div>
      </div>
    </div>
  );
}
