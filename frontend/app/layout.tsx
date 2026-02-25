import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import "./win98.css";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import { AuthProvider } from "@/lib/auth";
import { SWRProvider } from "@/lib/swr-provider";
import { AppShell } from "./app-shell";

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
        <SWRProvider>
          <AuthProvider>
            <AppShell>{children}</AppShell>
          </AuthProvider>
        </SWRProvider>
      </body>
    </html>
  );
}
