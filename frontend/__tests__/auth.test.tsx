import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import React from "react";

// Mock localStorage
const store: Record<string, string> = {};
vi.stubGlobal("localStorage", {
  getItem: (key: string) => store[key] ?? null,
  setItem: (key: string, value: string) => { store[key] = value; },
  removeItem: (key: string) => { delete store[key]; },
});

// Mock window.location.reload
const reloadMock = vi.fn();
Object.defineProperty(window, "location", {
  value: { reload: reloadMock },
  writable: true,
});

// Mock the API module
vi.mock("../lib/api", () => ({
  authAPI: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
  },
  setToken: vi.fn((t: string) => { store["auth_token"] = t; }),
  clearToken: vi.fn(() => { delete store["auth_token"]; }),
  getCurrentAdvertiserId: vi.fn(() => store["current_advertiser_id"] ?? null),
  setCurrentAdvertiserId: vi.fn((id: number) => { store["current_advertiser_id"] = String(id); }),
  clearCurrentAdvertiserId: vi.fn(() => { delete store["current_advertiser_id"]; }),
}));

import { authAPI, setToken, clearToken } from "../lib/api";
import { AuthProvider, useAuth } from "../lib/auth";

const mockedAuthAPI = vi.mocked(authAPI);

function wrapper({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

beforeEach(() => {
  vi.clearAllMocks();
  reloadMock.mockReset();
  Object.keys(store).forEach((k) => delete store[k]);
});

describe("useAuth - outside provider", () => {
  it("throws when used outside AuthProvider", () => {
    expect(() => {
      renderHook(() => useAuth());
    }).toThrow("useAuth must be used within AuthProvider");
  });
});

describe("useAuth - initial state", () => {
  it("starts with loading=true, user=null when no token", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    // Eventually loading becomes false
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toBeNull();
    expect(result.current.currentAdvertiserId).toBeNull();
  });

  it("fetches user on mount when token exists", async () => {
    store["auth_token"] = "existing-token";
    mockedAuthAPI.me.mockResolvedValueOnce({
      id: 1,
      email: "user@test.com",
      name: "Test",
      has_brand: true,
      advertisers: [
        { id: 10, company_name: "Auchan", sector: "supermarche" },
        { id: 20, company_name: "Lidl", sector: "supermarche" },
      ],
    });

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.user?.email).toBe("user@test.com");
    // Should auto-select first advertiser
    expect(result.current.currentAdvertiserId).toBe(10);
  });

  it("restores stored advertiser ID if valid", async () => {
    store["auth_token"] = "token";
    store["current_advertiser_id"] = "20";
    mockedAuthAPI.me.mockResolvedValueOnce({
      id: 1,
      email: "user@test.com",
      name: "Test",
      has_brand: true,
      advertisers: [
        { id: 10, company_name: "Auchan", sector: "supermarche" },
        { id: 20, company_name: "Lidl", sector: "supermarche" },
      ],
    });

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    // Should restore advertiser 20, not default to 10
    expect(result.current.currentAdvertiserId).toBe(20);
  });

  it("falls back to first advertiser if stored ID is invalid", async () => {
    store["auth_token"] = "token";
    store["current_advertiser_id"] = "999"; // doesn't exist
    mockedAuthAPI.me.mockResolvedValueOnce({
      id: 1,
      email: "user@test.com",
      name: "Test",
      has_brand: true,
      advertisers: [
        { id: 10, company_name: "Auchan", sector: "supermarche" },
      ],
    });

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.currentAdvertiserId).toBe(10);
  });

  it("clears token if /me fails (expired token)", async () => {
    store["auth_token"] = "expired-token";
    mockedAuthAPI.me.mockRejectedValueOnce(new Error("401"));

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toBeNull();
    expect(clearToken).toHaveBeenCalled();
  });
});

describe("useAuth - login", () => {
  it("stores token and sets user + first advertiser", async () => {
    mockedAuthAPI.login.mockResolvedValueOnce({
      token: "new-token",
      user: {
        id: 1,
        email: "a@b.com",
        name: "A",
        has_brand: true,
        advertisers: [
          { id: 5, company_name: "Carrefour", sector: "supermarche" },
          { id: 6, company_name: "Leclerc", sector: "supermarche" },
        ],
      },
    });

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.login("a@b.com", "pass");
    });

    expect(setToken).toHaveBeenCalledWith("new-token");
    expect(result.current.user?.email).toBe("a@b.com");
    expect(result.current.currentAdvertiserId).toBe(5);
  });

  it("handles login with no advertisers", async () => {
    mockedAuthAPI.login.mockResolvedValueOnce({
      token: "tok",
      user: { id: 1, email: "new@b.com", name: "New", has_brand: false, advertisers: [] },
    });

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.login("new@b.com", "pass");
    });

    expect(result.current.user?.has_brand).toBe(false);
    expect(result.current.currentAdvertiserId).toBeNull();
  });
});

describe("useAuth - logout", () => {
  it("clears everything", async () => {
    store["auth_token"] = "token";
    mockedAuthAPI.me.mockResolvedValueOnce({
      id: 1,
      email: "u@b.com",
      name: "U",
      has_brand: true,
      advertisers: [{ id: 10, company_name: "X", sector: "s" }],
    });

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.user).not.toBeNull());

    act(() => {
      result.current.logout();
    });

    expect(result.current.user).toBeNull();
    expect(result.current.currentAdvertiserId).toBeNull();
    expect(clearToken).toHaveBeenCalled();
  });
});

describe("useAuth - switchAdvertiser (multi-enseigne)", () => {
  it("updates advertiser ID and triggers page reload", async () => {
    store["auth_token"] = "token";
    mockedAuthAPI.me.mockResolvedValueOnce({
      id: 1,
      email: "u@b.com",
      name: "U",
      has_brand: true,
      advertisers: [
        { id: 10, company_name: "Auchan", sector: "supermarche" },
        { id: 20, company_name: "Lidl", sector: "supermarche" },
      ],
    });

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.currentAdvertiserId).toBe(10));

    act(() => {
      result.current.switchAdvertiser(20);
    });

    expect(result.current.currentAdvertiserId).toBe(20);
    expect(store["current_advertiser_id"]).toBe("20");
    expect(reloadMock).toHaveBeenCalledOnce();
  });
});
