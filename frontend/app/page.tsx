"use client";

import { useEffect, useState } from "react";
import {
  watchAPI,
  brandAPI,
  DashboardData,
  DashboardCompetitor,
  RankingCategory,
  AdIntelligence,
  SectorData,
  CompetitorSuggestionData,
  SetupResponseData,
} from "@/lib/api";
import { useAPI } from "@/lib/use-api";
import { formatNumber } from "@/lib/utils";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Instagram,
  Youtube,
  Star,
  Crown,
  AlertTriangle,
  Heart,
  Music,
  Smartphone,
  ArrowUpRight,
  ArrowDownRight,
  Zap,
  MessageSquare,
  Download,
  Shield,
  Activity,
  Target,
  ChevronUp,
  ChevronDown,
  BarChart3,
  Trophy,
  Users,
  Lightbulb,
  Megaphone,
  Play,
  Image,
  Layers,
  Monitor,
  Plus,
  Check,
  Globe,
  Rocket,
  Building2,
  ChevronRight,
  Store,
  Sparkles,
  Info,
  X,
} from "lucide-react";
import { PeriodFilter, PeriodDays } from "@/components/period-filter";

/* ─────────────────────── Helpers ─────────────────────── */

function TrendBadge({ value }: { value?: number }) {
  const v = value ?? 0;
  if (v === 0)
    return (
      <span className="inline-flex items-center gap-0.5 text-[11px] text-gray-400 tabular-nums">
        <Minus className="h-3 w-3" /> 0%
      </span>
    );
  if (v > 0)
    return (
      <span className="inline-flex items-center gap-0.5 text-[11px] font-semibold text-emerald-600 tabular-nums">
        <ArrowUpRight className="h-3 w-3" />+{v.toFixed(1)}%
      </span>
    );
  return (
    <span className="inline-flex items-center gap-0.5 text-[11px] font-semibold text-red-500 tabular-nums">
      <ArrowDownRight className="h-3 w-3" />{v.toFixed(1)}%
    </span>
  );
}

function Stars({ rating }: { rating: number }) {
  const full = Math.floor(rating);
  const half = rating - full >= 0.25;
  return (
    <span className="inline-flex items-center gap-px">
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          className={`h-3 w-3 ${
            i < full
              ? "fill-amber-400 text-amber-400"
              : i === full && half
              ? "fill-amber-400/50 text-amber-400"
              : "text-gray-200"
          }`}
        />
      ))}
    </span>
  );
}

function InsightIcon({ icon }: { icon: string }) {
  const c = "h-4 w-4";
  switch (icon) {
    case "crown": return <Crown className={c} />;
    case "trending-up": return <TrendingUp className={c} />;
    case "star": return <Star className={c} />;
    case "heart": return <Heart className={c} />;
    case "alert-triangle": return <AlertTriangle className={c} />;
    default: return <Zap className={c} />;
  }
}

function RankingIcon({ icon }: { icon: string }) {
  const c = "h-4 w-4";
  switch (icon) {
    case "trophy": return <Trophy className={c} />;
    case "instagram": return <Instagram className={c} />;
    case "music": return <Music className={c} />;
    case "youtube": return <Youtube className={c} />;
    case "star": return <Star className={c} />;
    case "heart": return <Heart className={c} />;
    case "users": return <Users className={c} />;
    default: return <BarChart3 className={c} />;
  }
}

function FormatIcon({ format }: { format: string }) {
  const c = "h-4 w-4";
  switch (format) {
    case "VIDEO": return <Play className={c} />;
    case "IMAGE": return <Image className={c} />;
    case "CAROUSEL": return <Layers className={c} />;
    case "DPA": return <Monitor className={c} />;
    case "DCO": return <Zap className={c} />;
    default: return <Megaphone className={c} />;
  }
}

function AppleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20.94c1.5 0 2.75 1.06 4 1.06 3 0 6-8 6-12.22A4.91 4.91 0 0 0 17 5c-2.22 0-4 1.44-5 2-1-.56-2.78-2-5-2a4.9 4.9 0 0 0-5 4.78C2 14 5 22 8 22c1.25 0 2.5-1.06 4-1.06Z" />
      <path d="M10 2c1 .5 2 2 2 5" />
    </svg>
  );
}

function ScoreInfoPanel({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-24" onClick={onClose}>
    <div className="fixed inset-0 bg-black/20" />
    <div className="relative rounded-xl border bg-card shadow-2xl p-4 space-y-3 text-sm max-w-md mx-4" onClick={e => e.stopPropagation()}>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold flex items-center gap-1.5">
          <Info className="h-4 w-4 text-violet-500" />
          Calcul du Score Global
        </h3>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>
      <p className="text-xs text-muted-foreground">
        Le score global (0&ndash;100) est un indice composite mesurant la maturite digitale d&apos;une enseigne. Il combine 3 dimensions complementaires :
      </p>
      <div className="space-y-2">
        <div className="flex items-center gap-3 p-2.5 rounded-lg bg-amber-50">
          <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-amber-100 shrink-0">
            <Star className="h-4 w-4 text-amber-600" />
          </div>
          <div className="flex-1">
            <div className="font-semibold text-xs flex items-center justify-between">
              <span>Note apps</span>
              <span className="text-amber-600 tabular-nums">40 pts</span>
            </div>
            <div className="text-[11px] text-muted-foreground">Moyenne des notes Play Store et App Store. Formule : (note / 5) &times; 40. Si une seule store est renseignee, elle est utilisee seule.</div>
          </div>
        </div>
        <div className="flex items-center gap-3 p-2.5 rounded-lg bg-pink-50">
          <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-pink-100 shrink-0">
            <Users className="h-4 w-4 text-pink-600" />
          </div>
          <div className="flex-1">
            <div className="font-semibold text-xs flex items-center justify-between">
              <span>Audience sociale</span>
              <span className="text-pink-600 tabular-nums">40 pts</span>
            </div>
            <div className="text-[11px] text-muted-foreground">Somme des followers Instagram + TikTok + abonnes YouTube. Formule : min(total / 1M, 1) &times; 40. Plafonne a 1M pour eviter la surponderation des geants.</div>
          </div>
        </div>
        <div className="flex items-center gap-3 p-2.5 rounded-lg bg-emerald-50">
          <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-emerald-100 shrink-0">
            <Download className="h-4 w-4 text-emerald-600" />
          </div>
          <div className="flex-1">
            <div className="font-semibold text-xs flex items-center justify-between">
              <span>Telechargements</span>
              <span className="text-emerald-600 tabular-nums">20 pts</span>
            </div>
            <div className="text-[11px] text-muted-foreground">Downloads Play Store (valeur numerique). Formule : min(downloads / 10M, 1) &times; 20. Indicateur d&apos;adoption mobile de l&apos;enseigne.</div>
          </div>
        </div>
      </div>
      <div className="text-[11px] space-y-1.5 border-t pt-2">
        <div className="flex items-start gap-1.5">
          <Trophy className="h-3.5 w-3.5 text-amber-500 mt-0.5 shrink-0" />
          <span className="text-muted-foreground"><strong className="text-foreground">100/100</strong> = note 5/5 + 1M+ followers + 10M+ downloads</span>
        </div>
        <div className="flex items-start gap-1.5">
          <Target className="h-3.5 w-3.5 text-violet-500 mt-0.5 shrink-0" />
          <span className="text-muted-foreground">Le score est relatif au secteur : comparez-vous a vos concurrents directs, pas en absolu</span>
        </div>
        <div className="flex items-start gap-1.5">
          <Activity className="h-3.5 w-3.5 text-blue-500 mt-0.5 shrink-0" />
          <span className="text-muted-foreground">Donnees mises a jour automatiquement chaque jour par notre collecteur</span>
        </div>
      </div>
    </div>
    </div>
  );
}

function BudgetInfoPanel({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-24" onClick={onClose}>
    <div className="fixed inset-0 bg-black/20" />
    <div className="relative rounded-xl border bg-card shadow-2xl p-4 space-y-3 text-sm max-w-md mx-4" onClick={e => e.stopPropagation()}>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold flex items-center gap-1.5">
          <Info className="h-4 w-4 text-emerald-500" />
          Estimation des budgets publicitaires
        </h3>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>
      <p className="text-xs text-muted-foreground">
        Les budgets affiches sont des <strong className="text-foreground">estimations fournies par Meta</strong> via la Bibliotheque publicitaire (Ad Library). Ce ne sont pas des chiffres exacts.
      </p>
      <div className="space-y-2">
        <div className="p-2.5 rounded-lg bg-blue-50 space-y-1">
          <div className="font-semibold text-xs text-blue-700 flex items-center gap-1.5">
            <BarChart3 className="h-3.5 w-3.5" />
            Source des donnees
          </div>
          <div className="text-[11px] text-muted-foreground">
            Meta fournit une fourchette <strong className="text-foreground">min&ndash;max</strong> pour chaque publicite dans l&apos;Ad Library. Cette fourchette represente la depense estimee en euros sur la duree de diffusion de la pub.
          </div>
        </div>
        <div className="p-2.5 rounded-lg bg-violet-50 space-y-1">
          <div className="font-semibold text-xs text-violet-700 flex items-center gap-1.5">
            <Layers className="h-3.5 w-3.5" />
            Methode de calcul
          </div>
          <div className="text-[11px] text-muted-foreground">
            Le budget total affiche est la <strong className="text-foreground">somme des fourchettes</strong> de toutes les pubs detectees pour un annonceur. Ex : 3 pubs avec des fourchettes de 100&ndash;200&euro;, 500&ndash;1000&euro; et 200&ndash;400&euro; = total de 800&ndash;1600&euro;.
          </div>
        </div>
        <div className="p-2.5 rounded-lg bg-amber-50 space-y-1">
          <div className="font-semibold text-xs text-amber-700 flex items-center gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5" />
            Limites
          </div>
          <ul className="text-[11px] text-muted-foreground space-y-0.5 ml-5 list-disc">
            <li>Les fourchettes Meta sont volontairement larges (ex : 0&ndash;100&euro;)</li>
            <li>Seules les pubs detectees sont comptees &mdash; certaines peuvent echapper a la collecte</li>
            <li>Le budget reel peut etre superieur si l&apos;annonceur utilise plusieurs pages</li>
            <li>Les pubs TikTok n&apos;ont pas de donnees budget (non fourni par TikTok)</li>
          </ul>
        </div>
      </div>
      <div className="text-[11px] text-muted-foreground border-t pt-2 flex items-start gap-1.5">
        <Shield className="h-3.5 w-3.5 text-emerald-500 mt-0.5 shrink-0" />
        <span>Toutes les donnees proviennent de la <strong className="text-foreground">Bibliotheque publicitaire de Meta</strong> (transparence UE). Aucune donnee privee n&apos;est utilisee.</span>
      </div>
    </div>
    </div>
  );
}

const RANK_COLORS = ["text-amber-500", "text-slate-400", "text-orange-400", "text-gray-400"];

const PRIORITY_STYLE: Record<string, string> = {
  high: "bg-red-50 border-red-200 text-red-800",
  medium: "bg-amber-50 border-amber-200 text-amber-800",
  info: "bg-indigo-50 border-indigo-200 text-indigo-800",
};

function BrandLogo({ name, logoUrl, size = "sm", className: extraClass = "" }: { name: string; logoUrl?: string; size?: "xs" | "sm" | "md" | "lg"; className?: string }) {
  const [imgErr, setImgErr] = useState(false);
  const dims = { xs: "h-5 w-5", sm: "h-7 w-7", md: "h-9 w-9", lg: "h-12 w-12" }[size];
  const textSize = { xs: "text-[9px]", sm: "text-[10px]", md: "text-xs", lg: "text-sm" }[size];
  const initials = name.split(/[\s&]+/).map(w => w[0]).join("").slice(0, 2).toUpperCase();

  if (logoUrl && !imgErr) {
    return (
      <img
        src={logoUrl}
        alt={name}
        className={`${dims} rounded-lg object-contain bg-white border border-border/50 shrink-0 ${extraClass}`}
        onError={() => setImgErr(true)}
      />
    );
  }
  return (
    <div className={`${dims} rounded-lg bg-gradient-to-br from-violet-100 to-indigo-100 flex items-center justify-center ${textSize} font-bold text-violet-600 shrink-0 ${extraClass}`}>
      {initials}
    </div>
  );
}

/* ─────────────────────── Onboarding ─────────────────────── */

function OnboardingScreen({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const FALLBACK_SECTORS: SectorData[] = [
    { code: "supermarche", name: "Grande Distribution", competitors_count: 6 },
    { code: "bricolage", name: "Bricolage & Maison", competitors_count: 2 },
    { code: "mode", name: "Mode & Habillement", competitors_count: 4 },
    { code: "beaute", name: "Beauté & Cosmétiques", competitors_count: 3 },
    { code: "electromenager", name: "Électroménager & High-Tech", competitors_count: 3 },
  ];
  const [sectors, setSectors] = useState<SectorData[]>(FALLBACK_SECTORS);
  const [sector, setSector] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [website, setWebsite] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [setupResult, setSetupResult] = useState<SetupResponseData | null>(null);
  const [selectedCompetitors, setSelectedCompetitors] = useState<Set<string>>(new Set());
  const [addedCount, setAddedCount] = useState(0);

  useEffect(() => {
    brandAPI.getSectors().then(setSectors).catch(() => {});
  }, []);

  async function handleSetup() {
    if (!companyName.trim() || !sector) return;
    setSubmitting(true);
    try {
      const result = await brandAPI.setup({
        company_name: companyName.trim(),
        sector,
        website: website.trim() || undefined,
      });
      setSetupResult(result);
      setSelectedCompetitors(new Set(result.suggested_competitors.map((c) => c.name)));
      setStep(2);
    } catch (e: any) {
      // Brand already exists → skip to dashboard
      if (e.status === 400 && e.message?.includes("déjà configurée")) {
        onComplete();
        return;
      }
      alert(e.message || "Erreur lors de la configuration");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAddCompetitors() {
    const names = Array.from(selectedCompetitors);
    if (names.length === 0) {
      setStep(3);
      return;
    }
    setSubmitting(true);
    try {
      const result = await brandAPI.addSuggestions(names);
      setAddedCount(result.added.length);
      setStep(3);
    } catch (e: any) {
      alert(e.message || "Erreur");
    } finally {
      setSubmitting(false);
    }
  }

  function toggleCompetitor(name: string) {
    setSelectedCompetitors((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  const channelIcons = (c: CompetitorSuggestionData) => {
    const channels = [];
    if (c.instagram_username) channels.push({ icon: Instagram, color: "text-pink-500", label: "IG" });
    if (c.tiktok_username) channels.push({ icon: Music, color: "text-cyan-600", label: "TT" });
    if (c.youtube_channel_id) channels.push({ icon: Youtube, color: "text-red-500", label: "YT" });
    if (c.playstore_app_id) channels.push({ icon: Smartphone, color: "text-emerald-600", label: "Play" });
    if (c.appstore_app_id) channels.push({ icon: Star, color: "text-blue-500", label: "Apple" });
    return channels;
  };

  // Step indicator
  const StepIndicator = () => (
    <div className="flex items-center justify-center gap-2 mb-8">
      {[1, 2, 3].map((s) => (
        <div key={s} className="flex items-center gap-2">
          <div className={`flex items-center justify-center h-8 w-8 rounded-full text-xs font-bold transition-all ${
            s < step ? "bg-violet-600 text-white" :
            s === step ? "bg-gradient-to-br from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-200/50" :
            "bg-muted text-muted-foreground"
          }`}>
            {s < step ? <Check className="h-4 w-4" /> : s}
          </div>
          {s < 3 && <div className={`w-12 h-0.5 rounded-full ${s < step ? "bg-violet-500" : "bg-muted"}`} />}
        </div>
      ))}
    </div>
  );

  if (step === 1) {
    return (
      <div className="flex items-center justify-center min-h-[70vh]">
        <div className="w-full max-w-lg">
          <StepIndicator />

          {/* Hero */}
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-3 mb-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-600 to-indigo-600 shadow-lg shadow-violet-200/50">
                <Sparkles className="h-6 w-6 text-white" />
              </div>
            </div>
            <h1 className="text-2xl font-bold tracking-tight mb-1">
              Bienvenue sur panoram<span className="bg-gradient-to-r from-violet-600 to-indigo-500 bg-clip-text text-transparent">AI</span>
            </h1>
            <p className="text-[11px] text-muted-foreground mb-2">
              by <span className="font-semibold">mobsuccess</span>
            </p>
            <p className="text-muted-foreground text-sm">
              Configurez votre enseigne pour lancer la veille concurrentielle
            </p>
          </div>

          {/* Form */}
          <div className="rounded-2xl border bg-card p-6 space-y-5">
            <div className="space-y-2">
              <label className="text-[13px] font-semibold text-foreground flex items-center gap-2">
                <Building2 className="h-4 w-4 text-violet-600" />
                Secteur d&apos;activite
              </label>
              <select
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                className="w-full h-10 rounded-lg border border-input bg-card px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-primary/50 transition-colors"
              >
                <option value="">Choisir un secteur...</option>
                {sectors.map((s) => (
                  <option key={s.code} value={s.code}>
                    {s.name} ({s.competitors_count} concurrents)
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-[13px] font-semibold text-foreground flex items-center gap-2">
                <Store className="h-4 w-4 text-violet-600" />
                Nom de votre enseigne
              </label>
              <input
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="ex: Auchan, Carrefour, Lidl..."
                className="w-full h-10 rounded-lg border border-input bg-card px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-primary/50 transition-colors placeholder:text-muted-foreground/60"
              />
            </div>

            <div className="space-y-2">
              <label className="text-[13px] font-semibold text-foreground flex items-center gap-2">
                <Globe className="h-4 w-4 text-violet-600" />
                Site web <span className="text-muted-foreground font-normal">(optionnel)</span>
              </label>
              <input
                type="url"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                placeholder="https://www.monenseigne.fr"
                className="w-full h-10 rounded-lg border border-input bg-card px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-primary/50 transition-colors placeholder:text-muted-foreground/60"
              />
            </div>

            <button
              onClick={handleSetup}
              disabled={!companyName.trim() || !sector || submitting}
              className="w-full h-11 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 text-white text-sm font-semibold shadow-sm hover:from-violet-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
            >
              {submitting ? (
                <>
                  <div className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                  Configuration...
                </>
              ) : (
                <>
                  Continuer
                  <ChevronRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (step === 2 && setupResult) {
    const suggestions = setupResult.suggested_competitors;
    return (
      <div className="flex items-center justify-center min-h-[70vh]">
        <div className="w-full max-w-2xl">
          <StepIndicator />

          <div className="text-center mb-6">
            <h2 className="text-xl font-bold tracking-tight mb-2">
              Selectionnez vos concurrents
            </h2>
            <p className="text-muted-foreground text-sm">
              {suggestions.length} concurrents suggeres pour le secteur{" "}
              <span className="font-semibold text-foreground">{setupResult.brand.sector_label}</span>
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
            {suggestions.map((c) => {
              const selected = selectedCompetitors.has(c.name);
              const channels = channelIcons(c);
              return (
                <button
                  key={c.name}
                  onClick={() => toggleCompetitor(c.name)}
                  className={`relative rounded-xl border p-4 text-left transition-all ${
                    selected
                      ? "border-violet-300 bg-violet-50/60 shadow-sm"
                      : "border-border bg-card hover:border-violet-200 hover:bg-muted/30"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className={`flex items-center justify-center h-8 w-8 rounded-lg shrink-0 transition-all ${
                      selected
                        ? "bg-violet-600 text-white"
                        : "bg-muted text-muted-foreground"
                    }`}>
                      {selected ? <Check className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                    </div>
                    <BrandLogo name={c.name} logoUrl={c.logo_url} size="sm" />
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold text-sm">{c.name}</div>
                      {c.website && (
                        <div className="text-[11px] text-muted-foreground truncate">{c.website}</div>
                      )}
                      <div className="flex items-center gap-1.5 mt-2">
                        {channels.map((ch) => (
                          <div key={ch.label} className={`${ch.color}`} title={ch.label}>
                            <ch.icon className="h-3.5 w-3.5" />
                          </div>
                        ))}
                        {channels.length === 0 && (
                          <span className="text-[10px] text-muted-foreground">Aucun canal configure</span>
                        )}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              {selectedCompetitors.size} selectionne{selectedCompetitors.size > 1 ? "s" : ""}
            </span>
            <button
              onClick={handleAddCompetitors}
              disabled={submitting}
              className="h-11 px-6 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 text-white text-sm font-semibold shadow-sm hover:from-violet-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2"
            >
              {submitting ? (
                <>
                  <div className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                  Ajout en cours...
                </>
              ) : (
                <>
                  <Rocket className="h-4 w-4" />
                  Lancer la veille
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (step === 3) {
    return (
      <div className="flex items-center justify-center min-h-[70vh]">
        <div className="w-full max-w-md text-center">
          <StepIndicator />

          <div className="flex items-center justify-center mb-6">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-500 shadow-lg shadow-emerald-200/50">
              <Check className="h-8 w-8 text-white" />
            </div>
          </div>

          <h2 className="text-xl font-bold tracking-tight mb-2">
            C&apos;est parti !
          </h2>
          <p className="text-muted-foreground text-sm mb-2">
            Votre enseigne <span className="font-semibold text-foreground">{setupResult?.brand.company_name}</span> est configuree.
          </p>
          {addedCount > 0 && (
            <p className="text-muted-foreground text-sm mb-6">
              {addedCount} concurrent{addedCount > 1 ? "s" : ""} ajout&eacute;{addedCount > 1 ? "s" : ""} a votre veille.
            </p>
          )}

          <button
            onClick={onComplete}
            className="h-11 px-8 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 text-white text-sm font-semibold shadow-sm hover:from-violet-700 hover:to-indigo-700 transition-all inline-flex items-center gap-2"
          >
            Acceder au dashboard
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    );
  }

  return null;
}

/* ─────────────────────── Page ─────────────────────── */

export default function DashboardPage() {
  const [activeRanking, setActiveRanking] = useState(0);
  const [showScoreInfo, setShowScoreInfo] = useState(false);
  const [showBudgetInfo, setShowBudgetInfo] = useState(false);
  const [periodDays, setPeriodDays] = useState<PeriodDays>(7);
  const [showAllAdvertisers, setShowAllAdvertisers] = useState(false);

  // SWR-cached dashboard fetch — survives page navigation
  const { data: swrData, error: swrError, isLoading: loading, mutate: refreshDashboard } = useAPI<DashboardData>(
    `/watch/dashboard?days=${periodDays}`
  );

  const data = swrData?.brand ? swrData : null;
  const needsOnboarding = swrData && !swrData.brand;
  const error = swrError
    ? (swrError as any).status === 404
      ? null
      : "Le serveur est en cours de démarrage, veuillez patienter..."
    : null;

  function loadDashboard() {
    refreshDashboard();
  }

  if (loading)
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-2 border-violet-200 border-t-violet-600 animate-spin" />
          <span className="text-sm text-muted-foreground">Chargement du dashboard...</span>
        </div>
      </div>
    );

  if (needsOnboarding)
    return <OnboardingScreen onComplete={loadDashboard} />;

  if (error || !data)
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center space-y-3">
          <AlertTriangle className="h-8 w-8 text-amber-400 mx-auto" />
          <p className="text-muted-foreground font-medium">{error || "Erreur inconnue"}</p>
          <button
            onClick={() => loadDashboard()}
            className="px-4 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700 transition-colors"
          >
            Réessayer
          </button>
        </div>
      </div>
    );

  const { brand, competitors, insights, platform_leaders: pl, ad_intelligence: adI, rankings } = data;
  const allPlayersSorted = [...(brand ? [brand, ...competitors] : competitors)].sort((a, b) => b.score - a.score);
  const allPlayers = brand ? [brand, ...competitors] : competitors;

  // Build platform rankings (top 3 per platform)
  const brandNameLower = data!.brand_name.toLowerCase();
  function buildPlatformRanking(
    getValue: (c: DashboardCompetitor) => number | undefined,
  ) {
    return allPlayers
      .map(c => ({ name: c.name, logo_url: c.logo_url, value: getValue(c) || 0, isBrand: c.name.toLowerCase() === brandNameLower }))
      .filter(c => c.value > 0)
      .sort((a, b) => b.value - a.value);
  }
  function buildAppRanking(key: "playstore" | "appstore") {
    return allPlayers
      .map(c => {
        const store = c[key] as any;
        return { name: c.name, logo_url: c.logo_url, value: store?.rating || 0, isBrand: c.name.toLowerCase() === brandNameLower };
      })
      .filter(c => c.value > 0)
      .sort((a, b) => b.value - a.value);
  }
  const igRanking = buildPlatformRanking(c => c.instagram?.followers);
  const ttRanking = buildPlatformRanking(c => c.tiktok?.followers);
  const ytRanking = buildPlatformRanking(c => c.youtube?.subscribers);
  const psRanking = buildAppRanking("playstore");
  const asRanking = buildAppRanking("appstore");

  return (
    <div className="space-y-8">
      {/* ── Hero header ────────────────────────────────── */}
      <div className="rounded-2xl bg-gradient-to-br from-indigo-950 via-[#1e1b4b] to-violet-950 p-5 sm:p-8 text-white relative overflow-hidden">
        <div className="absolute -top-20 -right-20 h-60 w-60 rounded-full bg-violet-400/[0.05]" />
        <div className="absolute -bottom-10 -left-10 h-40 w-40 rounded-full bg-indigo-400/[0.04]" />

        <div className="relative">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-6">
            <div>
              <div className="flex items-center gap-3 mb-1">
                {brand ? (
                  <BrandLogo name={brand.name} logoUrl={brand.logo_url} size="lg" className="border-white/20" />
                ) : (
                  <Shield className="h-6 w-6 text-violet-400" />
                )}
                <h1 className="text-2xl font-bold tracking-tight">{data.brand_name}</h1>
                {brand && (
                  <span className="relative inline-flex items-center gap-1">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                      brand.score >= 80 ? "bg-emerald-500/20 text-emerald-300" :
                      brand.score >= 50 ? "bg-amber-500/20 text-amber-300" :
                      "bg-red-500/20 text-red-300"
                    }`}>
                      Score {Math.round(brand.score)}/100
                    </span>
                    <button
                      onClick={() => setShowScoreInfo(!showScoreInfo)}
                      className="text-white/40 hover:text-white/80 transition-colors"
                      title="Comment le score est calcule ?"
                    >
                      <Info className="h-3.5 w-3.5" />
                    </button>
                    {showScoreInfo && (
                      <ScoreInfoPanel onClose={() => setShowScoreInfo(false)} />
                    )}
                  </span>
                )}
              </div>
              <p className="text-slate-400 text-sm">
                Veille concurrentielle &mdash; {data.sector}
              </p>
            </div>
            <div className="flex flex-col items-end gap-2">
              <PeriodFilter selectedDays={periodDays} onDaysChange={setPeriodDays} variant="dark" />
              <div className="text-[10px] text-slate-500 tabular-nums">
                Maj {(() => { try { return new Date(data.last_updated).toLocaleString("fr-FR"); } catch { return data.last_updated; } })()}
              </div>
            </div>
          </div>

          {/* Platform leader cards - comparative ranking */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {[
              { key: "instagram", ranking: igRanking, icon: <Instagram className="h-4 w-4" />, label: "Instagram", accent: "pink", unit: "followers", isRating: false },
              { key: "tiktok", ranking: ttRanking, icon: <Music className="h-4 w-4" />, label: "TikTok", accent: "cyan", unit: "followers", isRating: false },
              { key: "youtube", ranking: ytRanking, icon: <Youtube className="h-4 w-4" />, label: "YouTube", accent: "red", unit: "abonnés", isRating: false },
              { key: "playstore", ranking: psRanking, icon: <Smartphone className="h-4 w-4" />, label: "Play Store", accent: "emerald", unit: "note", isRating: true },
              { key: "appstore", ranking: asRanking, icon: <AppleIcon className="h-4 w-4" />, label: "App Store", accent: "blue", unit: "note", isRating: true },
            ].filter(p => p.ranking.length > 0).map((platform) => {
              const top3 = platform.ranking.slice(0, 3);
              const brandEntry = platform.ranking.find(e => e.isBrand);
              const brandRank = brandEntry ? platform.ranking.indexOf(brandEntry) + 1 : null;
              const accentMap: Record<string, { text: string; badge: string; bar: string }> = {
                pink: { text: "text-pink-400", badge: "bg-pink-500/20 text-pink-300", bar: "bg-pink-400" },
                cyan: { text: "text-cyan-400", badge: "bg-cyan-500/20 text-cyan-300", bar: "bg-cyan-400" },
                red: { text: "text-red-400", badge: "bg-red-500/20 text-red-300", bar: "bg-red-400" },
                emerald: { text: "text-emerald-400", badge: "bg-emerald-500/20 text-emerald-300", bar: "bg-emerald-400" },
                blue: { text: "text-blue-400", badge: "bg-blue-500/20 text-blue-300", bar: "bg-blue-400" },
              };
              const colors = accentMap[platform.accent];
              const maxVal = top3[0]?.value || 1;

              return (
                <div key={platform.key} className="rounded-xl bg-white/[0.06] backdrop-blur-sm px-4 py-3 border border-white/[0.08]">
                  {/* Header */}
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-1.5">
                      <span className={colors.text}>{platform.icon}</span>
                      <span className={`text-[9px] ${colors.text} uppercase tracking-widest font-semibold`}>{platform.label}</span>
                    </div>
                    <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-full ${colors.badge}`}>
                      {platform.ranking.length} acteurs
                    </span>
                  </div>

                  {/* Top 3 mini-ranking */}
                  <div className="space-y-1.5">
                    {top3.map((entry, idx) => {
                      const pct = platform.isRating ? (entry.value / 5) * 100 : (entry.value / maxVal) * 100;
                      return (
                        <div key={entry.name} className={`flex items-center gap-2 rounded-lg px-2 py-1.5 ${entry.isBrand ? "bg-violet-500/15 ring-1 ring-violet-400/30" : ""}`}>
                          <span className={`text-[10px] font-bold w-4 text-center shrink-0 ${
                            idx === 0 ? "text-amber-400" : idx === 1 ? "text-slate-400" : "text-orange-400/60"
                          }`}>
                            {idx === 0 ? "🥇" : idx === 1 ? "🥈" : "🥉"}
                          </span>
                          <BrandLogo name={entry.name} logoUrl={entry.logo_url} size="xs" className="border-white/10" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between">
                              <span className={`text-[11px] font-medium truncate ${entry.isBrand ? "text-violet-300" : "text-white/80"}`}>
                                {entry.name}
                              </span>
                              <span className="text-[11px] font-bold tabular-nums text-white shrink-0 ml-1">
                                {platform.isRating ? entry.value.toFixed(1) : formatNumber(entry.value)}
                              </span>
                            </div>
                            <div className="h-1 rounded-full bg-white/[0.08] mt-0.5 overflow-hidden">
                              <div className={`h-full rounded-full ${colors.bar} transition-all duration-700`} style={{ width: `${pct}%` }} />
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Brand position if not in top 3 */}
                  {brandEntry && brandRank && brandRank > 3 && (
                    <div className="mt-2 pt-1.5 border-t border-white/[0.06]">
                      <div className="flex items-center gap-2 px-2 py-1 rounded-lg bg-violet-500/10">
                        <span className="text-[10px] font-bold text-violet-400 w-4 text-center">#{brandRank}</span>
                        <BrandLogo name={brandEntry.name} logoUrl={brandEntry.logo_url} size="xs" className="border-white/10" />
                        <span className="text-[11px] text-violet-300 font-medium truncate flex-1">{brandEntry.name}</span>
                        <span className="text-[11px] font-bold tabular-nums text-violet-300">
                          {platform.isRating ? brandEntry.value.toFixed(1) : formatNumber(brandEntry.value)}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── RECOMMANDATIONS ─────────────────────────────── */}
      {adI.recommendations.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-100">
              <Lightbulb className="h-4 w-4 text-amber-600" />
            </div>
            <h2 className="text-[13px] font-semibold text-foreground">
              Recommandations strategiques
            </h2>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {adI.recommendations.map((rec, i) => (
              <div
                key={i}
                className={`flex items-start gap-3 p-4 rounded-xl border text-[13px] leading-relaxed ${PRIORITY_STYLE[rec.priority] || "bg-muted/30 border-border"}`}
              >
                <div className="mt-0.5 shrink-0">
                  {rec.priority === "high" ? <AlertTriangle className="h-4 w-4" /> :
                   rec.priority === "medium" ? <Lightbulb className="h-4 w-4" /> :
                   <Zap className="h-4 w-4" />}
                </div>
                <div>
                  <div className="font-medium mb-0.5">{rec.text}</div>
                  {rec.market_share_pct > 0 && (
                    <div className="flex items-center gap-2 mt-1.5">
                      <div className="h-1.5 w-20 rounded-full bg-black/10 overflow-hidden">
                        <div className="h-full rounded-full bg-current" style={{ width: `${Math.min(rec.market_share_pct, 100)}%` }} />
                      </div>
                      <span className="text-[10px] tabular-nums">{rec.market_share_pct}% du marche</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Rankings + Ad Intelligence ── */}
      <div className="space-y-6">

        {/* ── CLASSEMENTS ────────────────────────────────── */}
        <div className="space-y-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-100">
              <Trophy className="h-4 w-4 text-amber-600" />
            </div>
            <h2 className="text-[13px] font-semibold text-foreground">
              Classements
            </h2>
            <button
              onClick={() => setShowScoreInfo(!showScoreInfo)}
              className="ml-auto flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
            >
              <Info className="h-3 w-3" />
              Comment sont calcules les scores ?
            </button>
          </div>
          {showScoreInfo && (
            <ScoreInfoPanel onClose={() => setShowScoreInfo(false)} />
          )}

          {/* Ranking category tabs */}
          <div className="flex flex-wrap gap-1.5">
            {rankings.map((rk, idx) => (
              <button
                key={rk.id}
                onClick={() => setActiveRanking(idx)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  activeRanking === idx
                    ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-sm"
                    : "bg-card text-muted-foreground hover:bg-muted border border-border"
                }`}
              >
                <RankingIcon icon={rk.icon} />
                {rk.label}
              </button>
            ))}
          </div>

          {/* Active ranking leaderboard */}
          {rankings[activeRanking] && (
            <div className="rounded-2xl border bg-card overflow-hidden">
              <div className="divide-y">
                {rankings[activeRanking].entries.map((entry) => {
                  const isBrand = entry.is_brand;
                  return (
                    <div
                      key={entry.name}
                      className={`flex items-center gap-3 px-4 py-3 transition-colors ${
                        isBrand ? "bg-violet-50/60" : "hover:bg-muted/20"
                      }`}
                    >
                      <div className={`flex items-center justify-center h-7 w-7 rounded-lg text-xs font-bold ${
                        entry.rank === 1 ? "bg-amber-100 text-amber-700" :
                        entry.rank === 2 ? "bg-slate-100 text-slate-600" :
                        entry.rank === 3 ? "bg-orange-100 text-orange-600" :
                        "bg-gray-50 text-gray-500"
                      }`}>
                        {entry.rank === 1 ? <Crown className="h-3.5 w-3.5" /> : entry.rank}
                      </div>
                      <BrandLogo name={entry.name} logoUrl={(entry as any).logo_url} size="xs" />
                      <div className="flex-1 min-w-0">
                        <span className={`text-sm font-medium ${isBrand ? "text-violet-700" : ""}`}>
                          {entry.name}
                          {isBrand && <span className="ml-1.5 text-[9px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">Vous</span>}
                        </span>
                        {entry.extra && (
                          <span className="ml-2 text-[10px] text-muted-foreground">{entry.extra}</span>
                        )}
                      </div>
                      <div className="text-right">
                        <span className={`text-sm font-bold tabular-nums ${isBrand ? "text-violet-700" : ""}`}>
                          {entry.formatted}
                        </span>
                      </div>
                      {/* Visual bar */}
                      <div className="w-16 h-1.5 rounded-full bg-muted overflow-hidden">
                        <div
                          className={`h-full rounded-full ${isBrand ? "bg-violet-500" : "bg-foreground/20"}`}
                          style={{
                            width: `${rankings[activeRanking].entries.length > 0
                              ? (entry.value / rankings[activeRanking].entries[0].value) * 100
                              : 0}%`
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* ── INTELLIGENCE PUBLICITAIRE ───────────────────── */}
        <div className="space-y-4" id="ad-intelligence">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-100">
              <Megaphone className="h-4 w-4 text-violet-600" />
            </div>
            <h2 className="text-[13px] font-semibold text-foreground">
              Intelligence publicitaire
            </h2>
            <span className="ml-auto flex items-center gap-2">
              <span className="text-[11px] text-muted-foreground tabular-nums bg-muted px-2 py-0.5 rounded-full">{adI.total_ads} pubs</span>
              {adI.total_estimated_spend && adI.total_estimated_spend.max > 0 && (
                <span className="text-[11px] text-emerald-600 tabular-nums bg-emerald-50 px-2 py-0.5 rounded-full font-medium">
                  {formatNumber(adI.total_estimated_spend.min)}&ndash;{formatNumber(adI.total_estimated_spend.max)}&euro;
                </span>
              )}
              <button
                onClick={() => setShowBudgetInfo(!showBudgetInfo)}
                className="text-muted-foreground hover:text-violet-500 transition-colors"
                title="Comment le budget est estime"
              >
                <Info className="h-3.5 w-3.5" />
              </button>
            </span>
          </div>
          {showBudgetInfo && (
            <BudgetInfoPanel onClose={() => setShowBudgetInfo(false)} />
          )}

          {/* Ad intelligence grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

          {/* Ad volume comparison */}
          <div className="rounded-2xl border bg-card overflow-hidden">
            <div className="px-4 py-3 border-b bg-muted/20">
              <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Volume par annonceur / payeur
              </span>
            </div>
            <div className="divide-y">
              {adI.competitor_summary.map((cs) => {
                const maxAds = Math.max(...adI.competitor_summary.map(c => c.total_ads), 1);
                const pct = (cs.total_ads / maxAds) * 100;
                return (
                  <div key={cs.id} className={`px-4 py-3 ${cs.is_brand ? "bg-violet-50/60" : ""}`}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className={`text-sm font-medium flex items-center gap-2 ${cs.is_brand ? "text-violet-700" : ""}`}>
                        <BrandLogo name={cs.name} logoUrl={(cs as any).logo_url} size="xs" />
                        {cs.name}
                        {cs.is_brand && <span className="ml-1.5 text-[9px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">Vous</span>}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold tabular-nums">{cs.total_ads} pubs</span>
                        {(cs.estimated_spend_max ?? 0) > 0 && (
                          <span className="text-[10px] text-emerald-600 tabular-nums bg-emerald-50 px-1.5 py-0.5 rounded-md font-medium">
                            {formatNumber(cs.estimated_spend_min ?? 0)}&ndash;{formatNumber(cs.estimated_spend_max ?? 0)}&euro;
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-700 ${cs.is_brand ? "bg-violet-500" : "bg-violet-400"}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <div className="flex gap-1">
                        {Object.entries(cs.formats).slice(0, 3).map(([fmt, count]) => (
                          <span key={fmt} className="text-[9px] bg-muted px-1.5 py-0.5 rounded-md text-muted-foreground">
                            {fmt} ({count})
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="flex gap-1 mt-1.5">
                      {cs.platforms.map((p) => (
                        <span key={p} className="text-[9px] text-muted-foreground/60">{p}</span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right sub-column: Format + Platforms */}
          <div className="space-y-4">

          {/* Format breakdown */}
          <div className="rounded-2xl border bg-card overflow-hidden">
            <div className="px-4 py-3 border-b bg-muted/20">
              <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Formats publicitaires du marche
              </span>
            </div>
            <div className="p-4 grid grid-cols-2 sm:grid-cols-3 gap-3">
              {adI.format_breakdown.map((fb) => (
                <div key={fb.format} className="text-center rounded-xl bg-muted/30 p-3">
                  <FormatIcon format={fb.format} />
                  <div className="text-lg font-bold tabular-nums mt-1">{fb.pct}%</div>
                  <div className="text-[10px] text-muted-foreground">{fb.label}</div>
                  <div className="text-[10px] text-muted-foreground/60">{fb.count} pubs</div>
                </div>
              ))}
            </div>
          </div>

          {/* Platform diffusion breakdown */}
          <div className="rounded-2xl border bg-card overflow-hidden">
            <div className="px-4 py-3 border-b bg-muted/20">
              <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Plateformes de diffusion
              </span>
            </div>
            <div className="p-4 space-y-2.5">
              {adI.platform_breakdown.map((pb) => {
                const maxCount = Math.max(...adI.platform_breakdown.map(p => p.count), 1);
                const barPct = (pb.count / maxCount) * 100;
                return (
                  <div key={pb.platform} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium capitalize">{pb.platform.toLowerCase().replace("_", " ")}</span>
                      <span className="text-xs tabular-nums text-muted-foreground">{pb.count} pubs ({pb.pct}%)</span>
                    </div>
                    <div className="h-2 rounded-full bg-muted overflow-hidden">
                      <div className="h-full rounded-full bg-gradient-to-r from-violet-400 to-indigo-600 transition-all duration-700" style={{ width: `${barPct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
            {/* Per-competitor platform usage */}
            <div className="px-4 pb-4 pt-2 border-t">
              <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-2">Par concurrent</div>
              <div className="space-y-2">
                {adI.competitor_summary.map((cs) => (
                  <div key={cs.id} className="flex items-center gap-2 flex-wrap">
                    <span className={`text-[11px] font-semibold min-w-[80px] flex items-center gap-1.5 ${cs.is_brand ? "text-violet-700" : ""}`}>
                      <BrandLogo name={cs.name} logoUrl={(cs as any).logo_url} size="xs" />
                      {cs.name}
                    </span>
                    {cs.platforms.sort().map((p) => (
                      <span key={p} className="text-[9px] font-medium px-1.5 py-0.5 rounded bg-violet-50 text-violet-700 border border-violet-100">
                        {p.toLowerCase().replace("_", " ")}
                      </span>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </div>

          </div>{/* end right sub-column */}
          </div>{/* end ad intelligence grid */}
        </div>
      </div>

      {/* ── Insights strip ─────────────────────────────── */}
      {insights.length > 0 && (
        <div className="rounded-2xl border bg-card overflow-hidden">
          <div className="px-4 py-2.5 border-b bg-muted/20 flex items-center gap-2">
            <Activity className="h-3.5 w-3.5 text-indigo-500" />
            <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Insights
            </span>
            <span className="text-[10px] text-muted-foreground/60 ml-auto">{insights.length} signaux</span>
          </div>
          <div className="divide-y">
            {insights.map((ins, i) => {
              const sev = ins.severity;
              const dotColor =
                sev === "success" ? "bg-emerald-500" :
                sev === "warning" ? "bg-amber-500" :
                sev === "danger" ? "bg-red-500" :
                "bg-indigo-500";
              const iconColor =
                sev === "success" ? "text-emerald-500" :
                sev === "warning" ? "text-amber-500" :
                sev === "danger" ? "text-red-500" :
                "text-indigo-500";
              return (
                <div key={i} className="flex items-center gap-3 px-4 py-2.5 hover:bg-muted/20 transition-colors">
                  <div className={`shrink-0 ${iconColor}`}>
                    <InsightIcon icon={ins.icon} />
                  </div>
                  <span className="text-[13px] text-foreground/90">{ins.text}</span>
                  <div className={`ml-auto shrink-0 h-2 w-2 rounded-full ${dotColor}`} />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Competitor cards ───────────────────────────── */}
      <div className="space-y-5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100">
            <Users className="h-4 w-4 text-blue-600" />
          </div>
          <h2 className="text-[13px] font-semibold text-foreground">
            Concurrents
          </h2>
        </div>
        <div className="space-y-4">
          {[...competitors].sort((a, b) => b.score - a.score).map((comp) => {
            const maxSocial = Math.max(...competitors.map((c) => c.total_social), 1);
            const socialPct = (comp.total_social / maxSocial) * 100;
            const { instagram: ig, tiktok: tt, youtube: yt, playstore: ps, appstore: as_ } = comp;

            // Find ad data for this competitor
            const compAds = adI.competitor_summary.find(c => c.id === comp.id);

            return (
              <div
                key={comp.id}
                className="rounded-2xl border bg-card overflow-hidden transition-shadow hover:shadow-lg"
              >
                <div className="flex items-center gap-4 px-5 py-4">
                  <div className={`flex items-center justify-center h-9 w-9 rounded-xl text-sm font-bold ${
                    comp.rank === 1 ? "bg-gradient-to-br from-amber-400 to-yellow-500 text-white shadow-lg shadow-amber-200/40" :
                    comp.rank === 2 ? "bg-gradient-to-br from-slate-300 to-slate-400 text-white shadow-lg shadow-slate-200/40" :
                    comp.rank === 3 ? "bg-gradient-to-br from-orange-300 to-orange-400 text-white shadow-lg shadow-orange-200/40" :
                    "bg-gray-100 text-gray-500"
                  }`}>
                    {comp.rank === 1 ? <Crown className="h-4 w-4" /> : comp.rank}
                  </div>
                  <BrandLogo name={comp.name} logoUrl={comp.logo_url} size="md" />
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-lg truncate">{comp.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {formatNumber(comp.total_social)} reach social
                      {compAds && compAds.total_ads > 0 && (
                        <span className="ml-2">&middot; {compAds.total_ads} pubs actives</span>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`inline-flex items-center justify-center h-10 w-10 rounded-xl text-sm font-bold ${
                      comp.score >= 80 ? "bg-emerald-100 text-emerald-700" :
                      comp.score >= 50 ? "bg-amber-100 text-amber-700" :
                      "bg-red-100 text-red-700"
                    }`}>
                      {Math.round(comp.score)}
                    </div>
                  </div>
                </div>

                {/* Social reach bar */}
                <div className="px-5 pb-1">
                  <div className="h-1 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-blue-500 via-violet-500 to-pink-500 transition-all duration-1000"
                      style={{ width: `${socialPct}%` }}
                    />
                  </div>
                </div>

                {/* Metrics grid */}
                <div className="px-5 py-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                  <div className={`rounded-xl px-3 py-2.5 ${ig ? "bg-pink-50/70" : "bg-muted/30"}`}>
                    <div className="flex items-center gap-1.5 mb-1">
                      <Instagram className="h-3.5 w-3.5 text-pink-500" />
                      <span className="text-[10px] text-pink-600 font-semibold uppercase">IG</span>
                    </div>
                    {ig ? (
                      <div className="text-sm font-bold tabular-nums">{formatNumber(ig.followers)}</div>
                    ) : <div className="text-xs text-muted-foreground">&mdash;</div>}
                  </div>

                  <div className={`rounded-xl px-3 py-2.5 ${tt && tt.followers > 0 ? "bg-cyan-50/70" : "bg-muted/30"}`}>
                    <div className="flex items-center gap-1.5 mb-1">
                      <Music className="h-3.5 w-3.5 text-cyan-600" />
                      <span className="text-[10px] text-cyan-600 font-semibold uppercase">TT</span>
                    </div>
                    {tt && tt.followers > 0 ? (
                      <div className="text-sm font-bold tabular-nums">{formatNumber(tt.followers)}</div>
                    ) : <div className="text-xs text-muted-foreground">&mdash;</div>}
                  </div>

                  <div className={`rounded-xl px-3 py-2.5 ${yt ? "bg-red-50/70" : "bg-muted/30"}`}>
                    <div className="flex items-center gap-1.5 mb-1">
                      <Youtube className="h-3.5 w-3.5 text-red-500" />
                      <span className="text-[10px] text-red-600 font-semibold uppercase">YT</span>
                    </div>
                    {yt ? (
                      <div className="text-sm font-bold tabular-nums">{formatNumber(yt.subscribers)}</div>
                    ) : <div className="text-xs text-muted-foreground">&mdash;</div>}
                  </div>

                  <div className={`rounded-xl px-3 py-2.5 ${ps?.rating ? "bg-emerald-50/70" : "bg-muted/30"}`}>
                    <div className="flex items-center gap-1.5 mb-1">
                      <Smartphone className="h-3.5 w-3.5 text-emerald-600" />
                      <span className="text-[10px] text-emerald-700 font-semibold uppercase">Play</span>
                    </div>
                    {ps?.rating ? (
                      <div className="flex items-center gap-1">
                        <span className="text-sm font-bold tabular-nums">{ps.rating.toFixed(1)}</span>
                        <Stars rating={ps.rating} />
                      </div>
                    ) : <div className="text-xs text-muted-foreground">&mdash;</div>}
                  </div>

                  <div className={`rounded-xl px-3 py-2.5 ${as_?.rating ? "bg-blue-50/70" : "bg-muted/30"}`}>
                    <div className="flex items-center gap-1.5 mb-1">
                      <AppleIcon className="h-3.5 w-3.5 text-blue-600" />
                      <span className="text-[10px] text-blue-700 font-semibold uppercase">Apple</span>
                    </div>
                    {as_?.rating ? (
                      <div className="flex items-center gap-1">
                        <span className="text-sm font-bold tabular-nums">{as_.rating.toFixed(1)}</span>
                        <Stars rating={as_.rating} />
                      </div>
                    ) : <div className="text-xs text-muted-foreground">&mdash;</div>}
                  </div>

                  {/* Ad formats used */}
                  <div className="rounded-xl px-3 py-2.5 bg-violet-50/70">
                    <div className="flex items-center gap-1.5 mb-1">
                      <Megaphone className="h-3.5 w-3.5 text-violet-600" />
                      <span className="text-[10px] text-violet-700 font-semibold uppercase">Pubs</span>
                    </div>
                    {compAds && compAds.total_ads > 0 ? (
                      <>
                        <div className="text-sm font-bold tabular-nums">{compAds.total_ads}</div>
                        <div className="flex flex-wrap gap-0.5 mt-0.5">
                          {Object.keys(compAds.formats).slice(0, 3).map(f => (
                            <span key={f} className="text-[8px] bg-violet-100 text-violet-600 px-1 py-px rounded">{f}</span>
                          ))}
                        </div>
                      </>
                    ) : <div className="text-xs text-muted-foreground">Aucune</div>}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Vue comparative ───────────────────────────── */}
      <div className="space-y-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100">
            <BarChart3 className="h-4 w-4 text-slate-600" />
          </div>
          <h2 className="text-[13px] font-semibold text-foreground">
            Vue comparative
          </h2>
        </div>
        <div className="rounded-2xl border bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/30">
                  <th className="text-left px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground w-8">#</th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Acteur</th>
                  <th className="text-right px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                    <span className="inline-flex items-center gap-1"><Instagram className="h-3 w-3 text-pink-500" />IG</span>
                  </th>
                  <th className="text-right px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                    <span className="inline-flex items-center gap-1"><Music className="h-3 w-3 text-cyan-500" />TT</span>
                  </th>
                  <th className="text-right px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                    <span className="inline-flex items-center gap-1"><Youtube className="h-3 w-3 text-red-500" />YT</span>
                  </th>
                  <th className="text-right px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                    <span className="inline-flex items-center gap-1"><Star className="h-3 w-3 text-amber-500" />Apps</span>
                  </th>
                  <th className="text-right px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                    <span className="inline-flex items-center gap-1"><Megaphone className="h-3 w-3 text-violet-500" />Pubs</span>
                  </th>
                  <th className="text-right px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                    <button
                      onClick={() => setShowScoreInfo(!showScoreInfo)}
                      className="inline-flex items-center gap-1 hover:text-foreground transition-colors"
                      title="Comment le score est calcule"
                    >
                      Score <Info className="h-3 w-3" />
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody>
                {allPlayersSorted.map((comp, idx) => {
                  const isBrand = comp.name.toLowerCase() === data.brand_name.toLowerCase();
                  const compAds = adI.competitor_summary.find(c => c.id === comp.id);
                  return (
                    <tr
                      key={comp.id}
                      className={`border-b last:border-0 transition-colors ${
                        isBrand ? "bg-violet-50/60 hover:bg-violet-50" : "hover:bg-muted/20"
                      }`}
                    >
                      <td className="px-4 py-3">
                        <div className={`flex items-center justify-center h-6 w-6 rounded-md text-[11px] font-bold ${
                          idx === 0 ? "bg-amber-100 text-amber-700" :
                          idx === 1 ? "bg-slate-100 text-slate-600" :
                          idx === 2 ? "bg-orange-100 text-orange-600" :
                          "bg-gray-50 text-gray-500"
                        }`}>
                          {idx + 1}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`font-medium flex items-center gap-2 ${isBrand ? "text-violet-700" : ""}`}>
                          <BrandLogo name={comp.name} logoUrl={comp.logo_url} size="xs" />
                          {comp.name}
                          {isBrand && <span className="ml-1.5 text-[9px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">Vous</span>}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {comp.instagram ? formatNumber(comp.instagram.followers) : <span className="text-muted-foreground">&mdash;</span>}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {comp.tiktok && comp.tiktok.followers > 0 ? formatNumber(comp.tiktok.followers) : <span className="text-muted-foreground">&mdash;</span>}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {comp.youtube ? formatNumber(comp.youtube.subscribers) : <span className="text-muted-foreground">&mdash;</span>}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {comp.avg_app_rating ? comp.avg_app_rating.toFixed(1) : <span className="text-muted-foreground">&mdash;</span>}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {compAds && compAds.total_ads > 0 ? compAds.total_ads : <span className="text-muted-foreground">&mdash;</span>}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className={`inline-flex items-center justify-center px-2.5 py-1 rounded-lg text-xs font-bold ${
                          comp.score >= 80 ? "bg-emerald-100 text-emerald-700" :
                          comp.score >= 50 ? "bg-amber-100 text-amber-700" :
                          "bg-red-100 text-red-700"
                        }`}>
                          {Math.round(comp.score)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ── Payeurs & Annonceurs detail ────────────────── */}
      <div className={`grid gap-6 items-start ${adI.payers.length > 0 ? "grid-cols-1 lg:grid-cols-2" : "grid-cols-1"}`}>
        {/* Payeurs (qui paye les pubs) */}
        {adI.payers.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-100">
                <Shield className="h-4 w-4 text-emerald-600" />
              </div>
              <h2 className="text-[13px] font-semibold text-foreground">
                Payeurs
              </h2>
              <span className="ml-auto text-[11px] text-muted-foreground bg-muted px-2 py-0.5 rounded-full">{adI.payers.length} entités</span>
            </div>
            <div className="rounded-2xl border bg-card overflow-hidden">
              <div className="divide-y">
                {adI.payers.map((payer) => {
                  const maxTotal = Math.max(...adI.payers.map(p => p.total), 1);
                  const pct = (payer.total / maxTotal) * 100;
                  return (
                    <div key={payer.name} className="px-4 py-3">
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="font-medium text-sm truncate">{payer.name}</span>
                          {payer.is_explicit && (
                            <span className="shrink-0 text-[8px] bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">
                              Verifie
                            </span>
                          )}
                        </div>
                        <span className="text-sm font-bold tabular-nums shrink-0 ml-2">{payer.total}</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-muted overflow-hidden mb-1.5">
                        <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-teal-500" style={{ width: `${pct}%` }} />
                      </div>
                      <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                        <span className="text-emerald-600 font-medium">{payer.active} actives</span>
                        {payer.pages.length > 1 && (
                          <span>{payer.pages.length} pages</span>
                        )}
                        {payer.pages.length === 1 && payer.pages[0] !== payer.name && (
                          <span>via {payer.pages[0]}</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Annonceurs (pages qui diffusent) */}
        <div className="space-y-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-100">
              <Users className="h-4 w-4 text-violet-600" />
            </div>
            <h2 className="text-[13px] font-semibold text-foreground">
              Annonceurs (pages)
            </h2>
            <span className="ml-auto text-[11px] text-muted-foreground bg-muted px-2 py-0.5 rounded-full">{adI.advertisers.length} pages</span>
          </div>
          <div className="rounded-2xl border bg-card overflow-hidden">
            <div className="divide-y">
              {(() => {
                const ADV_LIMIT = 6;
                const visible = showAllAdvertisers ? adI.advertisers : adI.advertisers.slice(0, ADV_LIMIT);
                const hasMore = adI.advertisers.length > ADV_LIMIT;
                return (
                  <>
                    {visible.map((adv) => {
                      const maxTotal = Math.max(...adI.advertisers.map(a => a.total), 1);
                      const pct = (adv.total / maxTotal) * 100;
                      return (
                        <div key={adv.name} className="px-4 py-3">
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="font-medium text-sm truncate">{adv.name}</span>
                            <span className="text-sm font-bold tabular-nums shrink-0 ml-2">{adv.total}</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-muted overflow-hidden mb-1.5">
                            <div className="h-full rounded-full bg-gradient-to-r from-violet-400 to-purple-500" style={{ width: `${pct}%` }} />
                          </div>
                          <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                            <span className="text-violet-600 font-medium">{adv.active} actives</span>
                            {adv.top_format && (
                              <span className="bg-muted px-1.5 py-0.5 rounded">Top: {adv.top_format}</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                    {hasMore && (
                      <button
                        onClick={() => setShowAllAdvertisers(v => !v)}
                        className="w-full px-4 py-2.5 text-xs font-medium text-violet-600 hover:bg-muted/30 transition-colors"
                      >
                        {showAllAdvertisers ? "Réduire" : `Voir tout (${adI.advertisers.length})`}
                      </button>
                    )}
                  </>
                );
              })()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
