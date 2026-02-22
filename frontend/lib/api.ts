export const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api").trim();

export interface Competitor {
  id: number;
  name: string;
  website?: string;
  logo_url?: string;
  facebook_page_id?: string;
  instagram_username?: string;
  tiktok_username?: string;
  youtube_channel_id?: string;
  playstore_app_id?: string;
  appstore_app_id?: string;
  snapchat_entity_name?: string;
  snapchat_username?: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
}

export interface CompetitorListItem {
  id: number;
  name: string;
  website?: string;
  logo_url?: string;
  global_score: number;
  rank: number;
  app_rating?: number;
  app_downloads?: string;
  instagram_followers?: number;
  tiktok_followers?: number;
  youtube_subscribers?: number;
  trend?: string;
  active_channels: string[];
  facebook_page_id?: string;
  instagram_username?: string;
  tiktok_username?: string;
  youtube_channel_id?: string;
  playstore_app_id?: string;
  appstore_app_id?: string;
  snapchat_entity_name?: string;
  snapchat_username?: string;
  created_at?: string;
}

export interface CompetitorCreate {
  name: string;
  website?: string;
  facebook_page_id?: string;
  instagram_username?: string;
  tiktok_username?: string;
  youtube_channel_id?: string;
  playstore_app_id?: string;
  appstore_app_id?: string;
  snapchat_entity_name?: string;
  snapchat_username?: string;
}

export interface DashboardStats {
  total_competitors: number;
  total_ads_tracked: number;
  total_apps_tracked: number;
  competitors_with_instagram: number;
  recent_activity: Activity[];
}

export interface Activity {
  type: string;
  competitor: string;
  description: string;
  date: string;
}

export interface Ad {
  id: number;
  competitor_id: number;
  ad_id: string;
  platform: string;
  creative_url?: string;
  ad_text?: string;
  cta?: string;
  start_date?: string;
  end_date?: string;
  is_active: boolean;
  estimated_spend_min?: number;
  estimated_spend_max?: number;
  impressions_min?: number;
  impressions_max?: number;
  created_at: string;
  publisher_platforms?: string[];
  page_id?: string;
  page_name?: string;
  page_categories?: string[];
  page_like_count?: number;
  page_profile_uri?: string;
  page_profile_picture_url?: string;
  link_url?: string;
  display_format?: string;
  targeted_countries?: string[];
  ad_categories?: string[];
  contains_ai_content?: boolean;
  ad_library_url?: string;
  title?: string;
  link_description?: string;
  byline?: string;
  disclaimer_label?: string;
  payer?: string;
  beneficiary?: string;
  age_min?: number;
  age_max?: number;
  gender_audience?: string;
  location_audience?: { name: string; type: string; excluded: boolean; num_obfuscated?: number }[];
  eu_total_reach?: number;
  age_country_gender_reach?: {
    country: string;
    age_gender_breakdowns: {
      age_range: string;
      male: number;
      female: number;
      unknown: number;
    }[];
  }[];
  // Creative Analysis (AI-powered)
  creative_concept?: string;
  creative_hook?: string;
  creative_tone?: string;
  creative_text_overlay?: string;
  creative_dominant_colors?: string[];
  creative_has_product?: boolean;
  creative_has_face?: boolean;
  creative_has_logo?: boolean;
  creative_layout?: string;
  creative_cta_style?: string;
  creative_score?: number;
  creative_tags?: string[];
  creative_summary?: string;
  creative_analyzed_at?: string;
  // Product classification (AI-powered)
  product_category?: string;
  product_subcategory?: string;
  ad_objective?: string;
  // Ad type segmentation
  ad_type?: string;  // "branding" | "performance" | "dts"
  // Enriched creative fields
  promo_type?: string;
  creative_format?: string;
  price_visible?: boolean;
  price_value?: string;
  seasonal_event?: string;
}

export interface InstagramData {
  id: number;
  competitor_id: number;
  followers: number;
  following: number;
  posts_count: number;
  avg_likes?: number;
  avg_comments?: number;
  engagement_rate?: number;
  bio?: string;
  recorded_at: string;
}

export interface TikTokData {
  id: number;
  competitor_id: number;
  username: string;
  followers: number;
  following: number;
  likes: number;
  videos_count: number;
  bio?: string;
  verified: boolean;
  recorded_at: string;
}

export interface YouTubeData {
  id: number;
  competitor_id: number;
  channel_id: string;
  channel_name?: string;
  subscribers: number;
  total_views: number;
  videos_count: number;
  avg_views?: number;
  avg_likes?: number;
  avg_comments?: number;
  engagement_rate?: number;
  description?: string;
  recorded_at: string;
}

export interface AppData {
  id: number;
  competitor_id: number;
  store: string;
  app_id: string;
  app_name: string;
  rating?: number;
  reviews_count?: number;
  downloads?: string;
  version?: string;
  last_updated?: string;
  description?: string;
  changelog?: string;
  recorded_at: string;
}

export interface DashboardCompetitorSocial {
  followers: number;
  growth_7d: number;
  engagement_rate?: number;
  posts?: number;
  likes?: number;
  videos?: number;
}

export interface DashboardCompetitorYouTube {
  subscribers: number;
  growth_7d: number;
  views: number;
  videos: number;
}

export interface DashboardCompetitorApp {
  app_name: string;
  rating: number | null;
  reviews: number | null;
  downloads?: string;
  version?: string;
}

export interface DashboardCompetitorSnapchat {
  ads_count: number;
  total_impressions: number;
  entity_name?: string;
}

export interface DashboardCompetitor {
  id: number;
  name: string;
  logo_url?: string;
  score: number;
  rank: number;
  instagram: DashboardCompetitorSocial | null;
  tiktok: DashboardCompetitorSocial | null;
  youtube: DashboardCompetitorYouTube | null;
  playstore: DashboardCompetitorApp | null;
  appstore: DashboardCompetitorApp | null;
  snapchat: DashboardCompetitorSnapchat | null;
  total_social: number;
  avg_app_rating: number | null;
  rank_among_all?: number;
  total_players?: number;
}

export interface DashboardInsight {
  type: string;
  icon: string;
  text: string;
  severity: "info" | "success" | "warning" | "danger";
}

export interface PlatformLeader {
  leader: string;
  value: number;
}

export interface AdFormatBreakdown {
  format: string;
  label: string;
  count: number;
  pct: number;
}

export interface AdPlatformBreakdown {
  platform: string;
  count: number;
  pct: number;
}

export interface AdAdvertiser {
  name: string;
  total: number;
  active: number;
  top_format: string | null;
}

export interface AdPayer {
  name: string;
  total: number;
  active: number;
  pages: string[];
  is_explicit: boolean;
}

export interface AdCompetitorSummary {
  id: number;
  name: string;
  is_brand: boolean;
  total_ads: number;
  active_ads: number;
  formats: Record<string, number>;
  platforms: string[];
  estimated_spend_min?: number;
  estimated_spend_max?: number;
}

export interface AdRecommendation {
  type: string;
  priority: "high" | "medium" | "info";
  format: string;
  label: string;
  text: string;
  used_by?: string[];
  market_share_pct: number;
}

export interface AdIntelligence {
  total_ads: number;
  total_active: number;
  total_estimated_spend?: { min: number; max: number };
  format_breakdown: AdFormatBreakdown[];
  platform_breakdown: AdPlatformBreakdown[];
  advertisers: AdAdvertiser[];
  payers: AdPayer[];
  competitor_summary: AdCompetitorSummary[];
  recommendations: AdRecommendation[];
}

export interface RankingEntry {
  rank: number;
  name: string;
  value: number;
  formatted: string;
  is_brand: boolean;
  extra?: string;
}

export interface RankingCategory {
  id: string;
  label: string;
  icon: string;
  entries: RankingEntry[];
}

export interface DashboardData {
  brand_name: string;
  sector: string;
  last_updated: string;
  freshness?: Record<string, string | null>;
  brand: DashboardCompetitor | null;
  competitors: DashboardCompetitor[];
  insights: DashboardInsight[];
  platform_leaders: Record<string, PlatformLeader>;
  ad_intelligence: AdIntelligence;
  rankings: RankingCategory[];
}

export interface WatchOverview {
  brand_name: string;
  sector: string;
  last_updated: string;
  position: {
    global_rank: number;
    total_players: number;
    global_score: number;
    score_trend?: string;
  };
  key_metrics: {
    id: string;
    label: string;
    my_value?: number;
    my_formatted: string;
    best_competitor: string;
    best_value: number;
    best_formatted: string;
    my_rank: number;
    trend?: string;
  }[];
  summary: string;
  alerts_count: number;
  critical_alerts: number;
}

// Auth token management
function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("auth_token");
}

export function setToken(token: string) {
  localStorage.setItem("auth_token", token);
}

export function clearToken() {
  localStorage.removeItem("auth_token");
}

// Advertiser switching
export function getCurrentAdvertiserId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("current_advertiser_id");
}

export function setCurrentAdvertiserId(id: number) {
  localStorage.setItem("current_advertiser_id", String(id));
}

export function clearCurrentAdvertiserId() {
  localStorage.removeItem("current_advertiser_id");
}

async function fetchAPI<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const token = getToken();
  const advertiserId = getCurrentAdvertiserId();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options?.headers as Record<string, string>) || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  if (advertiserId) {
    headers["X-Advertiser-Id"] = advertiserId;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const err = new Error(error.detail || `API Error: ${response.status}`);
    (err as any).status = response.status;
    throw err;
  }

  return response.json();
}

// Auth API
export interface AdvertiserSummary {
  id: number;
  company_name: string;
  sector: string;
  logo_url?: string;
}

export interface AuthUser {
  id: number;
  email: string;
  name: string;
  has_brand: boolean;
  brand_name?: string;
  is_admin?: boolean;
  advertisers?: AdvertiserSummary[];
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

export const authAPI = {
  register: (email: string, password: string, name?: string) =>
    fetchAPI<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    }),

  login: (email: string, password: string) =>
    fetchAPI<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => fetchAPI<AuthUser>("/auth/me"),
};

// Competitors API
export const competitorsAPI = {
  list: (opts?: { includeBrand?: boolean }) =>
    fetchAPI<CompetitorListItem[]>(`/competitors/${opts?.includeBrand ? "?include_brand=true" : ""}`),

  get: (id: number) => fetchAPI<Competitor>(`/competitors/${id}`),

  create: (data: CompetitorCreate) =>
    fetchAPI<Competitor>("/competitors/", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (id: number, data: Partial<CompetitorCreate>) =>
    fetchAPI<Competitor>(`/competitors/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  delete: (id: number) =>
    fetchAPI<{ message: string }>(`/competitors/${id}`, {
      method: "DELETE",
    }),

  getDashboard: () => fetchAPI<DashboardStats>("/competitors/dashboard"),

  lookup: (q: string) => fetchAPI<CompetitorCreate[]>(`/competitors/lookup?q=${encodeURIComponent(q)}`),

  getAnalysis: (id: number) => fetchAPI<any>(`/competitors/${id}/analysis`),

  enrich: (id: number) =>
    fetchAPI<{ message: string; results: Record<string, any> }>(`/competitors/${id}/enrich`, {
      method: "POST",
    }),

  suggestChildPages: (id: number) =>
    fetchAPI<{ competitor_id: number; competitor_name: string; main_page_id: string; suggestions: any[]; existing_children: string[] }>(`/competitors/${id}/suggest-child-pages`, {
      method: "POST",
    }),
};

// Watch/Overview API
export const watchAPI = {
  getOverview: () => fetchAPI<WatchOverview>("/watch/overview"),
  getDashboard: (days?: number) => fetchAPI<DashboardData>(`/watch/dashboard${days ? `?days=${days}` : ""}`),
  getAlerts: () => fetchAPI<any[]>("/watch/alerts"),
  getRankings: () => fetchAPI<any>("/watch/rankings"),
};

// Facebook Ads API
export const facebookAPI = {
  getAllAds: (activeOnly = false) =>
    fetchAPI<(Ad & { competitor_name: string })[]>(
      `/facebook/ads/all?active_only=${activeOnly}`
    ),

  getAds: (competitorId: number, activeOnly = true) =>
    fetchAPI<Ad[]>(
      `/facebook/ads/${competitorId}?active_only=${activeOnly}`
    ),

  fetchAds: async (competitorId: number, country = "FR") => {
    // Launch background fetch
    const launch = await fetchAPI<{ message: string; status: string }>(
      `/facebook/fetch/${competitorId}?country=${country}`,
      { method: "POST" }
    );
    // Poll until done (max 5 minutes)
    const maxPolls = 60;
    for (let i = 0; i < maxPolls; i++) {
      await new Promise((r) => setTimeout(r, 5000));
      const status = await fetchAPI<{ status: string; total_fetched?: number; new_stored?: number; message?: string }>(
        `/facebook/fetch/${competitorId}/status`
      );
      if (status.status === "completed") {
        return { message: status.message || "Done", total_fetched: status.total_fetched || 0, new_stored: status.new_stored || 0 };
      }
      if (status.status === "error") {
        throw new Error(status.message || "Fetch failed");
      }
    }
    return { message: launch.message, total_fetched: 0, new_stored: 0 };
  },

  getStats: (competitorId: number) =>
    fetchAPI<any>(`/facebook/stats/${competitorId}`),

  getComparison: () => fetchAPI<any[]>("/facebook/comparison"),

  enrichTransparency: () =>
    fetchAPI<{ message: string; enriched: number; errors: number }>(
      "/facebook/enrich-transparency",
      { method: "POST" }
    ),

  resolvePageIds: () =>
    fetchAPI<{ message: string; resolved: any[]; errors: any[] }>(
      "/facebook/resolve-page-ids",
      { method: "POST" }
    ),
};

// Instagram API
export const instagramAPI = {
  getData: (competitorId: number, limit = 30) =>
    fetchAPI<InstagramData[]>(
      `/instagram/data/${competitorId}?limit=${limit}`
    ),

  getLatest: (competitorId: number) =>
    fetchAPI<InstagramData>(`/instagram/latest/${competitorId}`),

  fetch: (competitorId: number) =>
    fetchAPI<{ message: string; data: any }>(
      `/instagram/fetch/${competitorId}`,
      { method: "POST" }
    ),

  getComparison: (days?: number) => fetchAPI<any[]>(`/instagram/comparison${days ? `?days=${days}` : ""}`),
};

// TikTok API
export const tiktokAPI = {
  getData: (competitorId: number, limit = 30) =>
    fetchAPI<TikTokData[]>(
      `/tiktok/data/${competitorId}?limit=${limit}`
    ),

  getLatest: (competitorId: number) =>
    fetchAPI<TikTokData>(`/tiktok/latest/${competitorId}`),

  fetch: (competitorId: number) =>
    fetchAPI<{ message: string; data: any }>(
      `/tiktok/fetch/${competitorId}`,
      { method: "POST" }
    ),

  getComparison: (days?: number) => fetchAPI<any[]>(`/tiktok/comparison${days ? `?days=${days}` : ""}`),

  getVideos: (competitorId: number) =>
    fetchAPI<any>(`/tiktok/videos/${competitorId}`),

  // TikTok Ads
  getAllAds: () =>
    fetchAPI<(Ad & { competitor_name: string })[]>("/tiktok/ads/all"),

  getAds: (competitorId: number) =>
    fetchAPI<Ad[]>(`/tiktok/ads/${competitorId}`),

  fetchAds: (competitorId: number) =>
    fetchAPI<{ message: string; ads_detected: number; new_stored: number }>(
      `/tiktok/ads/fetch/${competitorId}`,
      { method: "POST" }
    ),

  fetchAllAds: () =>
    fetchAPI<{ message: string; results: any[] }>(
      "/tiktok/ads/fetch-all",
      { method: "POST" }
    ),
};

// YouTube API
export const youtubeAPI = {
  getData: (competitorId: number, limit = 30) =>
    fetchAPI<YouTubeData[]>(
      `/youtube/data/${competitorId}?limit=${limit}`
    ),

  getLatest: (competitorId: number) =>
    fetchAPI<YouTubeData>(`/youtube/latest/${competitorId}`),

  fetch: (competitorId: number) =>
    fetchAPI<{ message: string; data: any }>(
      `/youtube/fetch/${competitorId}`,
      { method: "POST" }
    ),

  getComparison: (days?: number) => fetchAPI<any[]>(`/youtube/comparison${days ? `?days=${days}` : ""}`),

  getVideos: (competitorId: number) =>
    fetchAPI<any>(`/youtube/videos/${competitorId}`),
};

// Play Store API
export const playstoreAPI = {
  getData: (competitorId: number, limit = 30) =>
    fetchAPI<AppData[]>(`/playstore/data/${competitorId}?limit=${limit}`),

  getLatest: (competitorId: number) =>
    fetchAPI<AppData>(`/playstore/latest/${competitorId}`),

  fetch: (competitorId: number) =>
    fetchAPI<{ message: string; data: any }>(
      `/playstore/fetch/${competitorId}`,
      { method: "POST" }
    ),

  getComparison: (days?: number) => fetchAPI<any[]>(`/playstore/comparison${days ? `?days=${days}` : ""}`),

  getReviews: (competitorId: number) =>
    fetchAPI<any>(`/playstore/reviews/${competitorId}`),

  getTrends: (competitorId: number) =>
    fetchAPI<any>(`/playstore/trends/${competitorId}`),
};

// App Store API
export const appstoreAPI = {
  getData: (competitorId: number, limit = 30) =>
    fetchAPI<AppData[]>(`/appstore/data/${competitorId}?limit=${limit}`),

  getLatest: (competitorId: number) =>
    fetchAPI<AppData>(`/appstore/latest/${competitorId}`),

  fetch: (competitorId: number) =>
    fetchAPI<{ message: string; data: any }>(
      `/appstore/fetch/${competitorId}`,
      { method: "POST" }
    ),

  getComparison: (days?: number) => fetchAPI<any[]>(`/appstore/comparison${days ? `?days=${days}` : ""}`),

  getReviews: (competitorId: number) =>
    fetchAPI<any>(`/appstore/reviews/${competitorId}`),

  getTrends: (competitorId: number) =>
    fetchAPI<any>(`/appstore/trends/${competitorId}`),

  search: (query: string) =>
    fetchAPI<any[]>(`/appstore/search?query=${encodeURIComponent(query)}`),
};

// ASO Analysis API
export const asoAPI = {
  getAnalysis: () => fetchAPI<any>("/aso/analysis"),
};

// Global Enrichment API
export const enrichAPI = {
  enrichAll: () =>
    fetchAPI<{
      message: string;
      competitors_count: number;
      total_tasks: number;
      ok: number;
      skipped: number;
      errors: number;
      details: any[];
    }>("/enrich/all", { method: "POST" }),
};

// Google Ads API
export const googleAdsAPI = {
  getAllAds: (activeOnly = false) =>
    fetchAPI<(Ad & { competitor_name: string })[]>(
      `/google/ads/all?active_only=${activeOnly}`
    ),

  getAds: (competitorId: number) =>
    fetchAPI<any>(`/google/ads/${competitorId}`),

  fetchAds: (competitorId: number, country = "FR") =>
    fetchAPI<{ competitor: string; domain: string; fetched: number; new: number; updated: number }>(
      `/google/fetch/${competitorId}?country=${country}`,
      { method: "POST" }
    ),

  fetchAll: (country = "FR") =>
    fetchAPI<{ message: string; results: any[] }>(
      `/google/fetch-all?country=${country}`,
      { method: "POST" }
    ),
};

// Snapchat Ads API
export interface SnapchatComparison {
  competitor_id: number;
  competitor_name: string;
  ads_count: number;
  impressions_total: number;
  entity_name?: string;
  subscribers?: number;
  engagement_rate?: number;
  spotlight_count?: number;
  story_count?: number;
}

export const snapchatAPI = {
  getAllAds: () =>
    fetchAPI<(Ad & { competitor_name: string })[]>("/snapchat/ads/all"),

  getAds: (competitorId: number) =>
    fetchAPI<Ad[]>(`/snapchat/ads/${competitorId}`),

  getComparison: () =>
    fetchAPI<SnapchatComparison[]>("/snapchat/comparison"),

  fetchAds: (competitorId: number) =>
    fetchAPI<{ message: string; ads_detected: number; new_stored: number }>(
      `/snapchat/ads/fetch/${competitorId}`,
      { method: "POST" }
    ),

  fetchAllAds: () =>
    fetchAPI<{ message: string; results: any[] }>(
      "/snapchat/ads/fetch-all",
      { method: "POST" }
    ),

  fetchProfile: (competitorId: number) =>
    fetchAPI<{ message: string; subscribers: number; engagement_rate: number }>(
      `/snapchat/profile/fetch?competitor_id=${competitorId}`,
      { method: "POST" }
    ),

  getProfileComparison: () =>
    fetchAPI<SnapchatComparison[]>("/snapchat/profile/comparison"),
};

// Brand / Mon Compte API
export interface BrandProfileData {
  id: number;
  company_name: string;
  sector: string;
  sector_label: string;
  website?: string;
  logo_url?: string;
  playstore_app_id?: string;
  appstore_app_id?: string;
  instagram_username?: string;
  tiktok_username?: string;
  youtube_channel_id?: string;
  snapchat_entity_name?: string;
  channels_configured: number;
  competitors_tracked: number;
  created_at: string;
}

export interface SectorData {
  code: string;
  name: string;
  competitors_count: number;
}

export interface CompetitorSuggestionData {
  name: string;
  website?: string;
  logo_url?: string;
  sector: string;
  playstore_app_id?: string;
  appstore_app_id?: string;
  instagram_username?: string;
  tiktok_username?: string;
  youtube_channel_id?: string;
  snapchat_entity_name?: string;
  already_tracked: boolean;
}

export interface BrandSetupData {
  company_name: string;
  sector: string;
  website?: string;
  playstore_app_id?: string;
  appstore_app_id?: string;
  instagram_username?: string;
  tiktok_username?: string;
  youtube_channel_id?: string;
  snapchat_entity_name?: string;
}

export interface SetupResponseData {
  brand: BrandProfileData;
  suggested_competitors: CompetitorSuggestionData[];
  message: string;
}

export interface BrandListItem {
  id: number;
  company_name: string;
  sector: string;
  logo_url?: string;
}

export const brandAPI = {
  list: () => fetchAPI<BrandListItem[]>("/brand/list"),

  getSectors: () => fetchAPI<SectorData[]>("/brand/sectors"),

  setup: (data: BrandSetupData) =>
    fetchAPI<SetupResponseData>("/brand/setup", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getProfile: () => fetchAPI<BrandProfileData>("/brand/profile"),

  updateProfile: (data: BrandSetupData) =>
    fetchAPI<BrandProfileData>("/brand/profile", {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  getSuggestions: () =>
    fetchAPI<CompetitorSuggestionData[]>("/brand/suggestions"),

  addSuggestions: (names: string[]) =>
    fetchAPI<{ added: string[]; skipped: string[]; not_found: string[]; total_competitors: number }>(
      "/brand/suggestions/add",
      { method: "POST", body: JSON.stringify(names) }
    ),

  sync: () =>
    fetchAPI<{ message: string; competitor_id: number }>(
      "/brand/sync",
      { method: "POST" }
    ),

  suggestSocials: (companyName: string, website: string) =>
    fetchAPI<{ suggestions: Record<string, string>; detected: number; source: string }>(
      "/brand/suggest-socials",
      { method: "POST", body: JSON.stringify({ company_name: companyName, website }) }
    ),

  uploadLogo: async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    const advId = typeof window !== "undefined" ? localStorage.getItem("currentAdvertiserId") : null;
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (advId) headers["X-Advertiser-Id"] = advId;
    const res = await fetch(`${API_BASE}/brand/logo`, { method: "POST", headers, body: formData });
    if (!res.ok) throw new Error((await res.json()).detail || "Upload failed");
    return res.json() as Promise<{ message: string; logo_url: string }>;
  },
};

// Admin API
export interface AdminStats {
  brands: number;
  competitors: number;
  data_volume: {
    ads: number;
    instagram_records: number;
    tiktok_records: number;
    youtube_records: number;
    app_records: number;
    store_locations: number;
  };
  scheduler: {
    enabled: boolean;
    running: boolean;
    jobs: { id: string; name: string; next_run: string | null }[];
  };
}

export interface AdminUser {
  id: number;
  email: string;
  name: string;
  created_at: string | null;
  is_active: boolean;
  is_admin: boolean;
  has_brand: boolean;
  brand_name: string | null;
  competitors_count: number;
}

export interface PromptTemplateData {
  key: string;
  label: string;
  prompt_text: string;
  model_id: string;
  max_tokens: number;
  updated_at: string | null;
}

export interface GpsConflict {
  store_id: number;
  store_name: string;
  city: string;
  postal_code: string;
  store_lat: number;
  store_lng: number;
  banco_lat: number;
  banco_lng: number;
  banco_name: string;
  distance_m: number;
  gps_verified: boolean;
}

export interface GpsConflictsResponse {
  total_stores: number;
  conflicts_count: number;
  threshold_m: number;
  conflicts: GpsConflict[];
}

export interface DetectedPage {
  page_id: string;
  page_name: string;
  ads_count: number;
}

export interface SnapDetectedPage {
  page_name: string;
  ads_count: number;
}

export interface CompetitorPlatforms {
  facebook: {
    main_page_id: string | null;
    child_page_ids: string[];
    detected_pages: DetectedPage[];
    total_pages: number;
  };
  instagram: { handle: string | null; configured: boolean };
  tiktok: { handle: string | null; configured: boolean };
  youtube: { handle: string | null; configured: boolean };
  snapchat: { handle: string | null; username: string | null; configured: boolean; detected_pages: SnapDetectedPage[] };
  playstore: { handle: string | null; configured: boolean };
  appstore: { handle: string | null; configured: boolean };
  google: { ads_count: number; configured: boolean };
}

export interface PagesAuditCompetitor {
  id: number;
  name: string;
  is_brand: boolean;
  website: string | null;
  platforms: CompetitorPlatforms;
}

export interface PagesAuditSector {
  code: string;
  name: string;
  competitors: PagesAuditCompetitor[];
}

export interface SectorItem {
  code: string;
  name: string;
  competitors_count: number;
}

export const adminAPI = {
  getStats: () => fetchAPI<AdminStats>("/admin/stats"),
  getUsers: () => fetchAPI<AdminUser[]>("/admin/users"),
  getPrompts: () => fetchAPI<PromptTemplateData[]>("/admin/prompts"),
  updatePrompt: (key: string, data: { prompt_text: string; model_id?: string; max_tokens?: number }) =>
    fetchAPI<PromptTemplateData>(`/admin/prompts/${key}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  getGpsConflicts: (threshold = 200) =>
    fetchAPI<GpsConflictsResponse>(`/admin/gps-conflicts?threshold=${threshold}`),
  resolveGpsConflict: (storeId: number, chosen: "store" | "banco") =>
    fetchAPI<{ message: string; store_id: number }>(`/admin/gps-conflicts/${storeId}/resolve`, {
      method: "POST",
      body: JSON.stringify({ chosen }),
    }),
  getMethodologies: () =>
    fetchAPI<{ module: string; icon: string; fields: { key: string; label: string; description: string }[] }[]>(
      "/admin/methodologies"
    ),
  updateUser: (userId: number, data: { name?: string; email?: string; is_active?: boolean; is_admin?: boolean; password?: string }) =>
    fetchAPI<{ message: string; updated_fields: string[]; user: AdminUser }>(`/admin/users/${userId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  deleteUser: (userId: number) =>
    fetchAPI<{ message: string }>(`/admin/users/${userId}`, { method: "DELETE" }),
  getSectors: () => fetchAPI<SectorItem[]>("/admin/sectors"),
  getPagesAudit: (sector?: string) =>
    fetchAPI<PagesAuditSector[]>(`/admin/pages-audit${sector ? `?sector=${sector}` : ""}`),
  deletePage: (competitorId: number, platform: string, pageId?: string) =>
    fetchAPI<{ competitor: string; platform: string; action: string }>("/admin/pages-audit/delete", {
      method: "POST",
      body: JSON.stringify({ competitor_id: competitorId, platform, page_id: pageId }),
    }),
  deduplicate: () =>
    fetchAPI<{ merged: number; message: string }>("/admin/deduplicate", { method: "POST" }),
  updateCompetitor: (id: number, data: Partial<CompetitorCreate>) =>
    fetchAPI<{ message: string; updated_fields: string[]; competitor: Competitor }>(`/admin/competitors/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  reEnrich: (competitorId: number) =>
    fetchAPI<{ message: string; results: Record<string, any> }>(`/admin/re-enrich/${competitorId}`, { method: "POST" }),
  reEnrichAll: () =>
    fetchAPI<{ message: string; total: number; ok: number; errors: number; details: any[] }>("/admin/re-enrich-all", { method: "POST" }),
  getDataHealth: () =>
    fetchAPI<{
      total_competitors: number;
      never_enriched: { id: number; name: string }[];
      stale: { id: number; name: string; latest: string }[];
      coverage: Record<string, { count: number; pct: number }>;
      report: any[];
    }>("/admin/data-health"),
};

// Freshness API
export interface FreshnessData {
  instagram: string | null;
  tiktok: string | null;
  youtube: string | null;
  playstore: string | null;
  appstore: string | null;
  ads_meta: string | null;
  ads_google: string | null;
  ads_snapchat: string | null;
}

export const freshnessAPI = {
  get: () => fetchAPI<FreshnessData>("/freshness"),
};

// Creative Analysis API
export interface CreativeInsights {
  total_analyzed: number;
  avg_score: number;
  remaining?: number;
  concepts: { concept: string; count: number; pct: number }[];
  tones: { tone: string; count: number; pct: number }[];
  top_hooks: { hook: string; score: number; concept: string; competitor: string }[];
  colors: { color: string; count: number }[];
  top_performers: {
    ad_id: string;
    competitor_name: string;
    creative_url: string;
    score: number;
    concept: string;
    tone: string;
    summary: string;
    hook: string;
  }[];
  by_competitor: {
    competitor: string;
    count: number;
    avg_score: number;
    top_concept: string;
    top_tone: string;
  }[];
  categories: { category: string; count: number; pct: number }[];
  subcategories: { subcategory: string; count: number; pct: number }[];
  objectives: { objective: string; count: number; pct: number }[];
  promo_types?: { promo_type: string; count: number; pct: number }[];
  creative_formats?: { creative_format: string; count: number; pct: number }[];
  seasonal_events?: { seasonal_event: string; count: number; pct: number }[];
  recommendations: string[];
  signals: {
    type: string;
    icon: string;
    title: string;
    description: string;
    competitor: string;
    metric: string;
    severity: "high" | "medium" | "low";
  }[];
  geo_analysis: {
    location: string;
    ad_count: number;
    competitors: string[];
    top_category: string;
  }[];
}

export const creativeAPI = {
  analyzeAll: (limit = 10) =>
    fetchAPI<{ message: string; analyzed: number; errors: number; remaining: number }>(
      `/creative/analyze-all?limit=${limit}`,
      { method: "POST" }
    ),

  getInsights: (opts?: { competitor_id?: number; location?: string; category?: string }) => {
    const params = new URLSearchParams();
    if (opts?.competitor_id) params.set("competitor_id", String(opts.competitor_id));
    if (opts?.location) params.set("location", opts.location);
    if (opts?.category) params.set("category", opts.category);
    const qs = params.toString();
    return fetchAPI<CreativeInsights>(`/creative/insights${qs ? `?${qs}` : ""}`);
  },
};

// Social Content Analysis API
export interface ContentInsights {
  total_analyzed: number;
  avg_score: number;
  themes: { theme: string; count: number; pct: number }[];
  tones: { tone: string; count: number; pct: number }[];
  formats: { format: string; count: number; pct: number }[];
  top_hooks: { hook: string; score: number; theme: string; competitor: string; platform: string }[];
  top_hashtags: { hashtag: string; count: number }[];
  top_performers: {
    post_id: string;
    competitor_name: string;
    platform: string;
    title: string;
    description: string;
    url: string;
    thumbnail_url: string;
    score: number;
    theme: string;
    tone: string;
    hook: string;
    summary: string;
    views: number;
    likes: number;
  }[];
  by_competitor: {
    competitor: string;
    count: number;
    avg_score: number;
    top_theme: string;
    top_tone: string;
    total_views: number;
    total_likes: number;
  }[];
  by_platform: {
    platform: string;
    count: number;
    avg_score: number;
    total_views: number;
  }[];
  posting_frequency?: {
    by_competitor: { competitor: string; total_posts: number; avg_per_week: number; avg_per_month: number }[];
    day_distribution: { day: string; day_index: number; count: number }[];
  };
  posting_timing?: {
    hour_distribution: { hour: number; label: string; count: number; avg_engagement: number }[];
    best_slots: { day: string; day_index: number; hour: number; label: string; posts: number; avg_engagement: number }[];
    competitor_peak_hours: { competitor: string; peak_hour: number; peak_label: string; posts_at_peak: number }[];
  };
  best_tone_engagement?: { tone: string; avg_score: number; count: number };
  recommendations: string[];
}

// SEO / SERP Tracking API
export interface SerpRankingResult {
  position: number;
  competitor_name: string | null;
  competitor_id: number | null;
  domain: string;
  title: string;
  url: string;
}

export interface SerpRanking {
  keyword: string;
  results: SerpRankingResult[];
}

export interface SeoInsights {
  total_keywords: number;
  last_tracked: string | null;
  brand_name: string | null;
  brand_competitor_id: number | null;
  share_of_voice: { competitor: string; competitor_id: number; appearances: number; pct: number }[];
  avg_position: { competitor: string; competitor_id: number; avg_pos: number; keywords_in_top10: number }[];
  best_keywords: { competitor: string; competitor_id: number; keyword: string; position: number }[];
  missing_keywords: { competitor: string; competitor_id: number; keywords: string[] }[];
  top_domains: { domain: string; count: number }[];
  recommendations: string[];
  ai_analysis?: {
    diagnostic: string;
    priorities: { action: string; impact: string; effort: string; detail: string }[];
    quick_wins: string[];
    benchmark_insight: string;
  };
}

export const seoAPI = {
  track: () =>
    fetchAPI<{ tracked_keywords: number; total_results: number; matched_competitors: number; errors: any[] | null }>(
      "/seo/track",
      { method: "POST" }
    ),

  getRankings: () =>
    fetchAPI<{ keywords: SerpRanking[]; last_tracked: string | null }>("/seo/rankings"),

  getInsights: () => fetchAPI<SeoInsights>("/seo/insights"),
};

// GEO (Generative Engine Optimization) API
export interface GeoMention {
  competitor_name: string;
  competitor_id: number | null;
  position_in_answer: number;
  recommended: boolean;
  sentiment: string;
  context: string;
}

export interface GeoQueryResult {
  keyword: string;
  query: string;
  platforms: {
    claude: GeoMention[];
    gemini: GeoMention[];
    chatgpt: GeoMention[];
    mistral: GeoMention[];
  };
}

export interface GeoInsights {
  total_queries: number;
  platforms: string[];
  last_tracked: string | null;
  brand_name: string | null;
  brand_competitor_id: number | null;
  share_of_voice: { competitor: string; competitor_id: number; mentions: number; pct: number }[];
  avg_position: { competitor: string; competitor_id: number; avg_pos: number }[];
  recommendation_rate: { competitor: string; competitor_id: number; rate: number; recommended_count: number; total_mentions: number }[];
  sentiment: { competitor: string; competitor_id: number; positive: number; neutral: number; negative: number }[];
  platform_comparison: Record<string, any>[];
  key_criteria: { criterion: string; count: number }[];
  missing_keywords: { competitor: string; competitor_id: number; keywords: string[] }[];
  seo_vs_geo: { competitor: string; competitor_id: number; seo_pct: number; geo_pct: number; gap: number }[];
  recommendations: string[];
  ai_analysis?: {
    diagnostic: string;
    priorities: { action: string; impact: string; effort: string; detail: string }[];
    quick_wins: string[];
    benchmark_insight: string;
  };
}

export const geoTrackingAPI = {
  track: () =>
    fetchAPI<{ tracked_queries: number; platforms: string[]; total_mentions: number; matched_competitors: number }>(
      "/geo-tracking/track",
      { method: "POST" }
    ),

  getResults: () =>
    fetchAPI<{ queries: GeoQueryResult[]; last_tracked: string | null }>("/geo-tracking/results"),

  getInsights: () => fetchAPI<GeoInsights>("/geo-tracking/insights"),
};

// Signals API
export interface SignalItem {
  id: number;
  competitor_id: number;
  signal_type: string;
  severity: string;
  platform: string;
  title: string;
  description: string;
  metric_name: string;
  previous_value: number | null;
  current_value: number | null;
  change_percent: number | null;
  is_brand: boolean;
  is_read: boolean;
  detected_at: string;
}

export interface SignalSummary {
  total: number;
  unread: number;
  brand_signals: number;
  by_severity: Record<string, number>;
  by_platform: Record<string, number>;
}

export const signalsAPI = {
  list: (opts?: { severity?: string; platform?: string; unread_only?: boolean; limit?: number }) => {
    const params = new URLSearchParams();
    if (opts?.severity) params.set("severity", opts.severity);
    if (opts?.platform) params.set("platform", opts.platform);
    if (opts?.unread_only) params.set("unread_only", "true");
    if (opts?.limit) params.set("limit", String(opts.limit));
    const qs = params.toString();
    return fetchAPI<SignalItem[]>(`/signals/${qs ? `?${qs}` : ""}`);
  },

  summary: () => fetchAPI<SignalSummary>("/signals/summary"),

  markRead: (signalId: number) =>
    fetchAPI<{ ok: boolean }>(`/signals/mark-read/${signalId}`, { method: "POST" }),

  markAllRead: () =>
    fetchAPI<{ ok: boolean }>("/signals/mark-all-read", { method: "POST" }),

  detect: () =>
    fetchAPI<{ message: string; signals: any[]; snapshots: number }>("/signals/detect", { method: "POST" }),
};

// Ads Overview (Part de Voix)
export const adsOverviewAPI = {
  getOverview: (startDate?: string, endDate?: string) => {
    const params = new URLSearchParams();
    if (startDate) params.set("start_date", startDate);
    if (endDate) params.set("end_date", endDate);
    const qs = params.toString();
    return fetchAPI<any>(`/ads/overview${qs ? `?${qs}` : ""}`);
  },
};

export const socialContentAPI = {
  collectAll: () =>
    fetchAPI<{ message: string; new: number; updated: number; total_in_db: number; by_competitor: any[]; errors?: string[]; competitors_scanned?: number }>(
      "/social-content/collect-all",
      { method: "POST" }
    ),

  analyzeAll: (limit = 20) =>
    fetchAPI<{ message: string; analyzed: number; errors: number; remaining: number }>(
      `/social-content/analyze-all?limit=${limit}`,
      { method: "POST" }
    ),

  getInsights: (platform?: string) =>
    fetchAPI<ContentInsights>(`/social-content/insights${platform ? `?platform=${platform}` : ""}`),
};
