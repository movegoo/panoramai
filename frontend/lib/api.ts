export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

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

async function fetchAPI<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options?.headers as Record<string, string>) || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
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
export interface AuthUser {
  id: number;
  email: string;
  name: string;
  has_brand: boolean;
  brand_name?: string;
  is_admin?: boolean;
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
  list: () => fetchAPI<CompetitorListItem[]>("/competitors/"),

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

  getAnalysis: (id: number) => fetchAPI<any>(`/competitors/${id}/analysis`),
};

// Watch/Overview API
export const watchAPI = {
  getOverview: () => fetchAPI<WatchOverview>("/watch/overview"),
  getDashboard: () => fetchAPI<DashboardData>("/watch/dashboard"),
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

  fetchAds: (competitorId: number, country = "FR") =>
    fetchAPI<{ message: string; total_fetched: number; new_stored: number }>(
      `/facebook/fetch/${competitorId}?country=${country}`,
      { method: "POST" }
    ),

  getStats: (competitorId: number) =>
    fetchAPI<any>(`/facebook/stats/${competitorId}`),

  getComparison: () => fetchAPI<any[]>("/facebook/comparison"),

  enrichTransparency: () =>
    fetchAPI<{ message: string; enriched: number; errors: number }>(
      "/facebook/enrich-transparency",
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

  getComparison: () => fetchAPI<any[]>("/instagram/comparison"),
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

  getComparison: () => fetchAPI<any[]>("/tiktok/comparison"),

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

  getComparison: () => fetchAPI<any[]>("/youtube/comparison"),

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

  getComparison: () => fetchAPI<any[]>("/playstore/comparison"),

  getReviews: (competitorId: number) =>
    fetchAPI<any>(`/playstore/reviews/${competitorId}`),
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

  getComparison: () => fetchAPI<any[]>("/appstore/comparison"),

  getReviews: (competitorId: number) =>
    fetchAPI<any>(`/appstore/reviews/${competitorId}`),

  search: (query: string) =>
    fetchAPI<any[]>(`/appstore/search?query=${encodeURIComponent(query)}`),
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
}

export interface SetupResponseData {
  brand: BrandProfileData;
  suggested_competitors: CompetitorSuggestionData[];
  message: string;
}

export const brandAPI = {
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
};

// Admin API
export interface AdminStats {
  users: { total: number; active: number };
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

export const adminAPI = {
  getStats: () => fetchAPI<AdminStats>("/admin/stats"),
  getUsers: () => fetchAPI<AdminUser[]>("/admin/users"),
};
