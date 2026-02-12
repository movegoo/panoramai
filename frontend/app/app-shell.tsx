"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import { SidebarNav } from "./sidebar-nav";
import { Breadcrumb } from "./breadcrumb";
import { Menu, X } from "lucide-react";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const isLoginPage = pathname === "/login";

  // Close sidebar on route change
  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (loading) return;
    if (!user && !isLoginPage) {
      router.replace("/login");
    }
    if (user && isLoginPage) {
      router.replace("/");
    }
  }, [user, loading, isLoginPage, router]);

  const closeSidebar = useCallback(() => setSidebarOpen(false), []);

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-2 border-violet-200 border-t-violet-600 animate-spin" />
          <span className="text-sm text-muted-foreground">Chargement...</span>
        </div>
      </div>
    );
  }

  // Login page: no sidebar
  if (isLoginPage) {
    return <>{children}</>;
  }

  // Not authenticated: show nothing while redirecting
  if (!user) {
    return null;
  }

  // Authenticated: full app layout
  return (
    <div className="flex h-screen">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 lg:hidden"
          onClick={closeSidebar}
        />
      )}

      {/* Sidebar - hidden on mobile, shown on desktop */}
      <div
        className={`
          fixed inset-y-0 left-0 z-50 w-[220px] transform transition-transform duration-200 ease-in-out lg:relative lg:translate-x-0
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
        `}
      >
        <SidebarNav onClose={closeSidebar} />
      </div>

      <main className="flex-1 overflow-auto bg-background flex flex-col min-w-0">
        {/* Mobile header with hamburger */}
        <div className="lg:hidden flex items-center gap-3 px-4 py-3 border-b border-border bg-card/80 backdrop-blur-sm shrink-0">
          <button
            onClick={() => setSidebarOpen(true)}
            className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted transition-colors"
          >
            <Menu className="h-5 w-5 text-foreground" />
          </button>
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 shadow-sm">
              <span className="text-[10px] font-bold text-white">P</span>
            </div>
            <span className="text-[14px] font-bold tracking-tight text-foreground">
              panoram<span className="bg-gradient-to-r from-violet-600 to-indigo-500 bg-clip-text text-transparent">AI</span>
            </span>
          </div>
        </div>

        {/* Desktop breadcrumb */}
        <div className="hidden lg:block">
          <Breadcrumb />
        </div>

        <div className="flex-1 overflow-auto">
          <div className="mx-auto max-w-[1400px] px-4 sm:px-6 lg:px-8 py-4 sm:py-6">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
