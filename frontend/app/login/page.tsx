"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Sparkles, Mail, Lock, User, ChevronRight, AlertCircle } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (mode === "register") {
        await register(email, password, name || undefined);
      } else {
        await login(email, password);
      }
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Une erreur est survenue");
    } finally {
      setLoading(false);
    }
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
            {mode === "login" ? "Connectez-vous a votre compte" : "Creez votre compte"}
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="rounded-2xl border bg-card p-6 space-y-4 shadow-sm">
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          {mode === "register" && (
            <div className="space-y-1.5">
              <label className="text-[13px] font-medium text-foreground flex items-center gap-2">
                <User className="h-3.5 w-3.5 text-violet-600" />
                Nom
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Votre nom"
                className="w-full h-10 rounded-lg border border-input bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-primary/50 transition-colors placeholder:text-muted-foreground/60"
              />
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-[13px] font-medium text-foreground flex items-center gap-2">
              <Mail className="h-3.5 w-3.5 text-violet-600" />
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="vous@entreprise.com"
              required
              className="w-full h-10 rounded-lg border border-input bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-primary/50 transition-colors placeholder:text-muted-foreground/60"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-[13px] font-medium text-foreground flex items-center gap-2">
              <Lock className="h-3.5 w-3.5 text-violet-600" />
              Mot de passe
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === "register" ? "Min. 6 caracteres" : "Votre mot de passe"}
              required
              minLength={mode === "register" ? 6 : undefined}
              className="w-full h-10 rounded-lg border border-input bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-primary/50 transition-colors placeholder:text-muted-foreground/60"
            />
          </div>

          <button
            type="submit"
            disabled={loading || !email || !password}
            className="w-full h-11 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 text-white text-sm font-semibold shadow-sm hover:from-violet-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <div className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                {mode === "login" ? "Connexion..." : "Creation..."}
              </>
            ) : (
              <>
                {mode === "login" ? "Se connecter" : "Creer mon compte"}
                <ChevronRight className="h-4 w-4" />
              </>
            )}
          </button>

          <div className="text-center pt-2">
            <button
              type="button"
              onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
              className="text-sm text-violet-600 hover:text-violet-700 font-medium transition-colors"
            >
              {mode === "login"
                ? "Pas de compte ? Creer un compte"
                : "Deja un compte ? Se connecter"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
