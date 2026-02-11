import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import "leaflet/dist/leaflet.css";
import { SidebarNav } from "./sidebar-nav";
import { Breadcrumb } from "./breadcrumb";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "panoramAI - Veille Concurrentielle",
  description: "Cockpit de veille concurrentielle multi-canal",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body className={inter.className}>
        <div className="flex h-screen">
          {/* Sidebar */}
          <SidebarNav />

          {/* Main content */}
          <main className="flex-1 overflow-auto bg-background flex flex-col min-w-0">
            {/* Top bar with breadcrumb */}
            <Breadcrumb />

            {/* Content */}
            <div className="flex-1 overflow-auto">
              <div className="mx-auto max-w-[1400px] px-6 lg:px-8 py-6">
                {children}
              </div>
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
