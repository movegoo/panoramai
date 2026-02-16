import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock fetch
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Mock localStorage
const store: Record<string, string> = {};
vi.stubGlobal("localStorage", {
  getItem: (key: string) => store[key] ?? null,
  setItem: (key: string, value: string) => { store[key] = value; },
  removeItem: (key: string) => { delete store[key]; },
});

import {
  API_BASE,
  setCurrentAdvertiserId,
  getCurrentAdvertiserId,
  clearCurrentAdvertiserId,
  competitorsAPI,
  brandAPI,
  watchAPI,
  facebookAPI,
} from "../lib/api";

function mockJsonResponse(data: any, status = 200) {
  mockFetch.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
  });
}

beforeEach(() => {
  mockFetch.mockReset();
  Object.keys(store).forEach((k) => delete store[k]);
});

describe("Advertiser ID management", () => {
  it("setCurrentAdvertiserId stores in localStorage", () => {
    setCurrentAdvertiserId(42);
    expect(store["current_advertiser_id"]).toBe("42");
  });

  it("getCurrentAdvertiserId reads from localStorage", () => {
    store["current_advertiser_id"] = "10";
    expect(getCurrentAdvertiserId()).toBe("10");
  });

  it("getCurrentAdvertiserId returns null when empty", () => {
    expect(getCurrentAdvertiserId()).toBeNull();
  });

  it("clearCurrentAdvertiserId removes from localStorage", () => {
    store["current_advertiser_id"] = "10";
    clearCurrentAdvertiserId();
    expect(getCurrentAdvertiserId()).toBeNull();
  });
});

describe("X-Advertiser-Id header injection", () => {
  it("includes X-Advertiser-Id when advertiser is set", async () => {
    store["auth_token"] = "mytoken";
    store["current_advertiser_id"] = "42";
    mockJsonResponse([]);

    await competitorsAPI.list();

    const [, opts] = mockFetch.mock.calls[0];
    expect(opts.headers["X-Advertiser-Id"]).toBe("42");
    expect(opts.headers["Authorization"]).toBe("Bearer mytoken");
  });

  it("does NOT include X-Advertiser-Id when not set", async () => {
    store["auth_token"] = "mytoken";
    // No current_advertiser_id
    mockJsonResponse([]);

    await competitorsAPI.list();

    const [, opts] = mockFetch.mock.calls[0];
    expect(opts.headers["X-Advertiser-Id"]).toBeUndefined();
  });

  it("switches advertiser and subsequent calls use new ID", async () => {
    store["auth_token"] = "tok";
    store["current_advertiser_id"] = "10";

    // First call with advertiser 10
    mockJsonResponse([]);
    await competitorsAPI.list();
    expect(mockFetch.mock.calls[0][1].headers["X-Advertiser-Id"]).toBe("10");

    // Switch advertiser
    setCurrentAdvertiserId(20);

    // Second call with advertiser 20
    mockJsonResponse([]);
    await competitorsAPI.list();
    expect(mockFetch.mock.calls[1][1].headers["X-Advertiser-Id"]).toBe("20");
  });
});

describe("competitorsAPI", () => {
  it("list calls GET /competitors/", async () => {
    store["auth_token"] = "tok";
    mockJsonResponse([{ id: 1, name: "Carrefour" }]);

    const result = await competitorsAPI.list();
    expect(mockFetch.mock.calls[0][0]).toBe(`${API_BASE}/competitors/`);
    expect(result).toHaveLength(1);
  });

  it("list with includeBrand sends query param", async () => {
    store["auth_token"] = "tok";
    mockJsonResponse([]);

    await competitorsAPI.list({ includeBrand: true });
    expect(mockFetch.mock.calls[0][0]).toContain("include_brand=true");
  });

  it("create sends POST", async () => {
    store["auth_token"] = "tok";
    mockJsonResponse({ id: 2, name: "Lidl" });

    await competitorsAPI.create({ name: "Lidl", website: "https://lidl.fr" });
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe(`${API_BASE}/competitors/`);
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body).name).toBe("Lidl");
  });

  it("get calls GET /competitors/:id", async () => {
    store["auth_token"] = "tok";
    mockJsonResponse({ id: 1, name: "Carrefour" });

    await competitorsAPI.get(1);
    expect(mockFetch.mock.calls[0][0]).toBe(`${API_BASE}/competitors/1`);
  });

  it("delete sends DELETE", async () => {
    store["auth_token"] = "tok";
    mockJsonResponse({ message: "deleted" });

    await competitorsAPI.delete(1);
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe(`${API_BASE}/competitors/1`);
    expect(opts.method).toBe("DELETE");
  });

  it("enrich sends POST", async () => {
    store["auth_token"] = "tok";
    mockJsonResponse({ message: "ok", results: {} });

    await competitorsAPI.enrich(3);
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe(`${API_BASE}/competitors/3/enrich`);
    expect(opts.method).toBe("POST");
  });

  it("lookup sends query", async () => {
    store["auth_token"] = "tok";
    mockJsonResponse([{ name: "Carrefour" }]);

    await competitorsAPI.lookup("carr");
    expect(mockFetch.mock.calls[0][0]).toContain("/competitors/lookup?q=carr");
  });
});

describe("brandAPI", () => {
  it("getProfile calls GET /brand/profile", async () => {
    store["auth_token"] = "tok";
    mockJsonResponse({ id: 1, company_name: "Auchan" });

    await brandAPI.getProfile();
    expect(mockFetch.mock.calls[0][0]).toBe(`${API_BASE}/brand/profile`);
  });

  it("setup sends POST with brand data", async () => {
    store["auth_token"] = "tok";
    mockJsonResponse({ brand: {}, suggested_competitors: [], message: "ok" });

    await brandAPI.setup({ company_name: "Auchan", sector: "supermarche" });
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe(`${API_BASE}/brand/setup`);
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body).company_name).toBe("Auchan");
  });

  it("getSectors calls GET /brand/sectors", async () => {
    store["auth_token"] = "tok";
    mockJsonResponse([]);

    await brandAPI.getSectors();
    expect(mockFetch.mock.calls[0][0]).toBe(`${API_BASE}/brand/sectors`);
  });
});

describe("watchAPI", () => {
  it("getDashboard passes days param", async () => {
    store["auth_token"] = "tok";
    mockJsonResponse({});

    await watchAPI.getDashboard(30);
    expect(mockFetch.mock.calls[0][0]).toContain("/watch/dashboard?days=30");
  });

  it("getDashboard works without days param", async () => {
    store["auth_token"] = "tok";
    mockJsonResponse({});

    await watchAPI.getDashboard();
    expect(mockFetch.mock.calls[0][0]).toBe(`${API_BASE}/watch/dashboard`);
  });
});

describe("facebookAPI", () => {
  it("getAllAds sends active_only param", async () => {
    store["auth_token"] = "tok";
    mockJsonResponse([]);

    await facebookAPI.getAllAds(true);
    expect(mockFetch.mock.calls[0][0]).toContain("active_only=true");
  });

  it("fetchAds sends POST with country", async () => {
    store["auth_token"] = "tok";
    mockJsonResponse({ message: "ok", total_fetched: 0, new_stored: 0 });

    await facebookAPI.fetchAds(1, "FR");
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toContain("/facebook/fetch/1?country=FR");
    expect(opts.method).toBe("POST");
  });
});

describe("error propagation", () => {
  it("404 throws with detail message", async () => {
    store["auth_token"] = "tok";
    mockJsonResponse({ detail: "Concurrent non trouvé" }, 404);

    await expect(competitorsAPI.get(999)).rejects.toThrow("Concurrent non trouvé");
  });

  it("error includes status code", async () => {
    store["auth_token"] = "tok";
    mockJsonResponse({ detail: "Forbidden" }, 403);

    try {
      await competitorsAPI.get(1);
    } catch (e: any) {
      expect(e.status).toBe(403);
    }
  });
});
