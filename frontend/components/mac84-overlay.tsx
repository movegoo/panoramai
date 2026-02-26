"use client";

import { useEffect, useState, useRef } from "react";
import { usePathname } from "next/navigation";

/* ── Rainbow Apple Logo (SVG inline) ── */
function RainbowApple({ size = 48 }: { size?: number }) {
  return (
    <svg width={size} height={size * 1.22} viewBox="0 0 83 101" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Classic 6-color rainbow Apple logo */}
      <path d="M57.3 0c.4 3.6-1.1 7.2-3.5 9.8-2.4 2.7-6.3 4.7-10 4.4-.5-3.5 1.3-7.1 3.5-9.4C49.7 2.4 53.9.4 57.3 0z" fill="#61BB46"/>
      <path d="M74.8 33.4c-4.3 2.5-7.2 7-7.1 12.2.1 6.1 4.2 11.5 10 13.6-1.5 4.5-3.6 8.8-6.7 12.6-2.7 3.4-5.5 6.8-9.9 6.9-4.3.1-5.7-2.6-10.7-2.6-5 0-6.5 2.5-10.6 2.7-4.3.2-7.5-3.7-10.3-7.1-5.6-6.9-9.8-19.5-4.1-28 2.8-4.2 7.8-6.8 13.2-6.9 4.2-.1 8.1 2.8 10.7 2.8 2.5 0 7.3-3.5 12.3-3 2.1.1 8 .8 11.8 6.3-.3.2-7 4.1-6.6 12.5" fill="url(#rainbow)"/>
      <defs>
        <linearGradient id="rainbow" x1="23" y1="33" x2="23" y2="79" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#61BB46"/>
          <stop offset="0.17" stopColor="#FDB827"/>
          <stop offset="0.33" stopColor="#F5821F"/>
          <stop offset="0.5" stopColor="#E03A3E"/>
          <stop offset="0.67" stopColor="#963D97"/>
          <stop offset="1" stopColor="#009DDC"/>
        </linearGradient>
      </defs>
    </svg>
  );
}

/* ── Boot Screen (Happy Mac style) ── */
export function MacBootScreen({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const t1 = setTimeout(() => setStep(1), 400);
    const t2 = setTimeout(() => setStep(2), 1000);
    const t3 = setTimeout(() => setStep(3), 1600);
    const t4 = setTimeout(() => setStep(4), 2200);
    const t5 = setTimeout(() => onDone(), 3000);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4); clearTimeout(t5); };
  }, [onDone]);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 99999,
        background: "#f2f0e6",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: '"Chicago", "Geneva", "Monaco", monospace',
        fontSize: 12,
        color: "#000",
        cursor: "crosshair",
        imageRendering: "pixelated",
      }}
    >
      {/* Rainbow stripes at top */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, display: "flex", height: 6 }}>
        {["#61BB46", "#FDB827", "#F5821F", "#E03A3E", "#963D97", "#009DDC"].map((c) => (
          <div key={c} style={{ flex: 1, background: c }} />
        ))}
      </div>

      <div style={{ textAlign: "center", maxWidth: 400 }}>
        {/* Rainbow Apple logo */}
        <div style={{ marginBottom: 16, display: "flex", justifyContent: "center" }}>
          <RainbowApple size={56} />
        </div>

        {step >= 1 && (
          <div style={{ marginBottom: 12, fontSize: 18, fontWeight: "bold", letterSpacing: 2 }}>
            panoramAI
          </div>
        )}

        {step >= 1 && (
          <div style={{ fontSize: 10, color: "#666", marginBottom: 16 }}>
            Macintosh System 1.0 &bull; 1984
          </div>
        )}

        {step >= 2 && (
          <div style={{ textAlign: "left", marginLeft: 40, lineHeight: 1.8, fontSize: 11 }}>
            Chargement de Chicago.font ........... OK<br />
            Suppression des degradés ............. OK<br />
            Activation des pixels ................ OK
          </div>
        )}

        {step >= 3 && (
          <div style={{ textAlign: "left", marginLeft: 40, lineHeight: 1.8, fontSize: 11, marginTop: 4 }}>
            Remplacement de l&apos;interface .......... OK<br />
            Installation de la Barre de menu ...... OK
          </div>
        )}

        {step >= 4 && (
          <div style={{ marginTop: 20, fontSize: 11 }}>
            <div style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              border: "2px solid #000",
              borderRadius: 0,
              padding: "6px 24px",
              background: "#fff",
              boxShadow: "2px 2px 0 #000",
            }}>
              <span className="mac84-blink">&#9612;</span>
              Bienvenue sur Macintosh
            </div>
          </div>
        )}
      </div>

      {/* Rainbow stripes at bottom */}
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, display: "flex", height: 6 }}>
        {["#61BB46", "#FDB827", "#F5821F", "#E03A3E", "#963D97", "#009DDC"].map((c) => (
          <div key={c} style={{ flex: 1, background: c }} />
        ))}
      </div>

      <style>{`
        .mac84-blink {
          animation: mac84-cursor 1s steps(1) infinite;
        }
        @keyframes mac84-cursor {
          0%, 49% { opacity: 1; }
          50%, 100% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}

/* ── Menu bar (classic Mac top bar) ── */
const PAGE_TITLES: Record<string, string> = {
  "/": "Vue d'ensemble",
  "/competitors": "Concurrents",
  "/ads": "Publicités",
  "/social": "Réseaux Sociaux",
  "/apps": "Applications",
  "/geo": "Carte & Zones",
  "/seo": "SEO",
  "/geo-tracking": "GEO Tracking",
  "/vgeo": "Video GEO",
  "/account": "Mon enseigne",
};

export function Mac84MenuBar({ active, onToggle }: { active: boolean; onToggle: () => void }) {
  const [time, setTime] = useState("");
  const [appleOpen, setAppleOpen] = useState(false);
  const [fileOpen, setFileOpen] = useState(false);
  const pathname = usePathname();
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function tick() {
      const now = new Date();
      setTime(now.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }));
    }
    tick();
    const i = setInterval(tick, 30000);
    return () => clearInterval(i);
  }, []);

  useEffect(() => {
    if (!appleOpen && !fileOpen) return;
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setAppleOpen(false);
        setFileOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [appleOpen, fileOpen]);

  useEffect(() => { setAppleOpen(false); setFileOpen(false); }, [pathname]);

  if (!active) return null;

  const pageTitle = PAGE_TITLES[pathname] || "panoramAI";

  return (
    <div
      ref={menuRef}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        height: 22,
        zIndex: 99997,
        background: "#fff",
        borderBottom: "2px solid #000",
        display: "flex",
        alignItems: "center",
        fontFamily: '"Chicago", "Geneva", "Monaco", monospace',
        fontSize: 12,
        color: "#000",
        padding: "0 8px",
        userSelect: "none",
      }}
    >
      {/* Apple menu */}
      <div style={{ position: "relative" }}>
        <button
          onClick={() => { setAppleOpen(!appleOpen); setFileOpen(false); }}
          style={{
            background: appleOpen ? "#000" : "transparent",
            color: appleOpen ? "#fff" : "#000",
            border: "none",
            padding: "0 8px",
            height: 20,
            fontSize: 12,
            fontFamily: "inherit",
            cursor: "pointer",
            fontWeight: "bold",
            boxShadow: "none",
            minHeight: "auto",
          }}
        >
          &#63743;
        </button>

        {appleOpen && (
          <div style={{
            position: "absolute",
            top: 20,
            left: 0,
            width: 200,
            background: "#fff",
            border: "2px solid #000",
            boxShadow: "3px 3px 0 rgba(0,0,0,0.5)",
            zIndex: 99999,
          }}>
            <MacMenuItem label="A propos de panoramAI..." disabled />
            <div style={{ borderTop: "1px solid #000", margin: "2px 0" }} />
            <MacMenuItem label="Vue d'ensemble" onClick={() => { setAppleOpen(false); window.location.href = "/"; }} />
            <MacMenuItem label="Concurrents" onClick={() => { setAppleOpen(false); window.location.href = "/competitors"; }} />
            <MacMenuItem label="Publicités" onClick={() => { setAppleOpen(false); window.location.href = "/ads"; }} />
            <MacMenuItem label="Réseaux sociaux" onClick={() => { setAppleOpen(false); window.location.href = "/social"; }} />
            <div style={{ borderTop: "1px solid #000", margin: "2px 0" }} />
            <MacMenuItem label="Mode normal" shortcut="⌘Q" onClick={() => { setAppleOpen(false); onToggle(); }} />
          </div>
        )}
      </div>

      {/* File menu */}
      <div style={{ position: "relative" }}>
        <button
          onClick={() => { setFileOpen(!fileOpen); setAppleOpen(false); }}
          style={{
            background: fileOpen ? "#000" : "transparent",
            color: fileOpen ? "#fff" : "#000",
            border: "none",
            padding: "0 8px",
            height: 20,
            fontSize: 12,
            fontFamily: "inherit",
            cursor: "pointer",
            fontWeight: "bold",
            boxShadow: "none",
            minHeight: "auto",
          }}
        >
          Fichier
        </button>

        {fileOpen && (
          <div style={{
            position: "absolute",
            top: 20,
            left: 0,
            width: 180,
            background: "#fff",
            border: "2px solid #000",
            boxShadow: "3px 3px 0 rgba(0,0,0,0.5)",
            zIndex: 99999,
          }}>
            <MacMenuItem label="Nouveau" shortcut="⌘N" disabled />
            <MacMenuItem label="Ouvrir..." shortcut="⌘O" disabled />
            <div style={{ borderTop: "1px solid #000", margin: "2px 0" }} />
            <MacMenuItem label="Quitter" shortcut="⌘Q" onClick={() => { setFileOpen(false); onToggle(); }} />
          </div>
        )}
      </div>

      {/* Current window title */}
      <div style={{ flex: 1, textAlign: "center", fontWeight: "bold", fontSize: 12 }}>
        {pageTitle}
      </div>

      {/* Time */}
      <div style={{ fontSize: 12, fontVariantNumeric: "tabular-nums" }}>
        {time}
      </div>
    </div>
  );
}

function MacMenuItem({ label, shortcut, onClick, disabled }: { label: string; shortcut?: string; onClick?: () => void; disabled?: boolean }) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      onClick={disabled ? undefined : onClick}
      onMouseEnter={() => !disabled && setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        width: "100%",
        padding: "3px 16px",
        border: "none",
        background: hovered ? "#000" : "transparent",
        color: disabled ? "#999" : hovered ? "#fff" : "#000",
        cursor: disabled ? "default" : "pointer",
        fontSize: 12,
        fontFamily: "inherit",
        textAlign: "left",
        boxShadow: "none",
        minHeight: "auto",
        outline: "none",
      }}
    >
      <span>{label}</span>
      {shortcut && <span style={{ fontSize: 11, opacity: 0.7 }}>{shortcut}</span>}
    </button>
  );
}
