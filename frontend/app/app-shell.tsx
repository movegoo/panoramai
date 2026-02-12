"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { SidebarNav } from "./sidebar-nav";
import { Breadcrumb } from "./breadcrumb";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const isLoginPage = pathname === "/login";

  useEffect(() => {
    if (loading) return;
    if (!user && !isLoginPage) {
      router.replace("/login");
    }
    if (user && isLoginPage) {
      router.replace("/");
    }
  }, [user, loading, isLoginPage, router]);

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
      <SidebarNav />
      <main className="flex-1 overflow-auto bg-background flex flex-col min-w-0">
        <Breadcrumb />
        <div className="flex-1 overflow-auto">
          <div className="mx-auto max-w-[1400px] px-6 lg:px-8 py-6">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
