import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Mock localStorage
const store: Record<string, string> = {};
vi.stubGlobal("localStorage", {
  getItem: (key: string) => store[key] ?? null,
  setItem: (key: string, value: string) => { store[key] = value; },
  removeItem: (key: string) => { delete store[key]; },
});

// Import after mocks are set up
import { API_BASE, authAPI, setToken, clearToken } from "../lib/api";

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

describe("API_BASE", () => {
  it("defaults to localhost", () => {
    expect(API_BASE).toContain("localhost:8000");
  });
});

describe("token management", () => {
  it("setToken stores token", () => {
    setToken("abc123");
    expect(store["auth_token"]).toBe("abc123");
  });

  it("clearToken removes token", () => {
    store["auth_token"] = "abc123";
    clearToken();
    expect(store["auth_token"]).toBeUndefined();
  });
});

describe("authAPI.login", () => {
  it("calls correct endpoint with POST", async () => {
    mockJsonResponse({ token: "tok", user: { id: 1, email: "a@b.com" } });
    const result = await authAPI.login("a@b.com", "pass");
    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe(`${API_BASE}/auth/login`);
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body)).toEqual({ email: "a@b.com", password: "pass" });
    expect(result.token).toBe("tok");
  });

  it("throws on 401", async () => {
    mockJsonResponse({ detail: "Bad creds" }, 401);
    await expect(authAPI.login("a@b.com", "wrong")).rejects.toThrow("Bad creds");
  });
});

describe("authAPI.register", () => {
  it("calls correct endpoint", async () => {
    mockJsonResponse({ token: "tok", user: { id: 1, email: "new@b.com" } });
    await authAPI.register("new@b.com", "pass123", "New User");
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe(`${API_BASE}/auth/register`);
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body)).toEqual({
      email: "new@b.com",
      password: "pass123",
      name: "New User",
    });
  });
});

describe("authAPI.me", () => {
  it("sends auth header when token is set", async () => {
    store["auth_token"] = "mytoken";
    mockJsonResponse({ id: 1, email: "a@b.com", name: "Test" });
    await authAPI.me();
    const [, opts] = mockFetch.mock.calls[0];
    expect(opts.headers["Authorization"]).toBe("Bearer mytoken");
  });
});

describe("error handling", () => {
  it("throws with status on 500", async () => {
    mockJsonResponse({ detail: "Server error" }, 500);
    try {
      await authAPI.me();
    } catch (e: any) {
      expect(e.message).toBe("Server error");
      expect(e.status).toBe(500);
    }
  });
});
