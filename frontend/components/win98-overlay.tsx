"use client";

import { useEffect, useState, useRef } from "react";
import { usePathname } from "next/navigation";

export function BSODScreen({ onDone }: { onDone: () => void }) {
  const [showText, setShowText] = useState(0);

  useEffect(() => {
    const t1 = setTimeout(() => setShowText(1), 200);
    const t2 = setTimeout(() => setShowText(2), 800);
    const t3 = setTimeout(() => setShowText(3), 1400);
    const t4 = setTimeout(() => setShowText(4), 1900);
    const t5 = setTimeout(() => onDone(), 2400);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4); clearTimeout(t5); };
  }, [onDone]);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 99999,
        background: "#0000aa",
        color: "#c0c0c0",
        fontFamily: '"Courier New", "Fixedsys", monospace',
        fontSize: "13px",
        lineHeight: 1.5,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "40px",
        cursor: "none",
      }}
    >
      <div style={{ maxWidth: 620, width: "100%" }}>
        {showText >= 1 && (
          <div style={{ textAlign: "center", marginBottom: 20 }}>
            <span style={{ background: "#aaa", color: "#0000aa", padding: "1px 6px", fontWeight: "bold", letterSpacing: 1 }}>
              &nbsp;panoramAI&nbsp;
            </span>
          </div>
        )}

        {showText >= 1 && (
          <p>
            Une erreur fatale s&apos;est produite a 0028:C0034B03.<br />
            Le systeme de design actuel va etre remplace.
          </p>
        )}

        {showText >= 2 && (
          <p style={{ marginTop: 12 }}>
            &nbsp;&nbsp;* Suppression des coins arrondis .......... OK<br />
            &nbsp;&nbsp;* Remplacement des degradés ............... OK<br />
            &nbsp;&nbsp;* Chargement de Windows 98 UI ............. OK<br />
            &nbsp;&nbsp;* Installation Comic Sans ................ REFUSE
          </p>
        )}

        {showText >= 3 && (
          <p style={{ marginTop: 12 }}>
            &nbsp;&nbsp;* Application du fond Sarcelle ........... OK<br />
            &nbsp;&nbsp;* Barre des taches ....................... OK
          </p>
        )}

        {showText >= 4 && (
          <p style={{ marginTop: 20 }}>
            Appuyez sur une touche pour continuer <span className="win98-bsod-cursor">_</span>
          </p>
        )}
      </div>

      <style>{`
        .win98-bsod-cursor {
          animation: bsod-blink 1s steps(1) infinite;
        }
        @keyframes bsod-blink {
          0%, 49% { opacity: 1; }
          50%, 100% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}

const PAGE_TITLES: Record<string, string> = {
  "/": "Vue d'ensemble",
  "/competitors": "Concurrents",
  "/ads": "Publicités",
  "/social": "Réseaux Sociaux",
  "/apps": "Applications",
  "/map": "Carte & Zones",
  "/seo": "SEO",
  "/geo": "GEO",
  "/account": "Mon enseigne",
  "/admin": "Backoffice",
};

export function Win98Taskbar({ active, onToggle }: { active: boolean; onToggle: () => void }) {
  const [time, setTime] = useState("");
  const [startOpen, setStartOpen] = useState(false);
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

  // Close start menu on outside click
  useEffect(() => {
    if (!startOpen) return;
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setStartOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [startOpen]);

  // Close start menu on route change
  useEffect(() => { setStartOpen(false); }, [pathname]);

  if (!active) return null;

  const pageTitle = PAGE_TITLES[pathname] || "panoramAI";

  return (
    <>
      {/* Start menu */}
      {startOpen && (
        <div
          ref={menuRef}
          style={{
            position: "fixed",
            bottom: 30,
            left: 2,
            width: 200,
            zIndex: 99998,
            background: "#c0c0c0",
            boxShadow: "inset -1px -1px 0 #0a0a0a, inset 1px 1px 0 #fff, inset -2px -2px 0 #808080, inset 2px 2px 0 #dfdfdf, 4px 4px 0 rgba(0,0,0,0.25)",
            fontFamily: '"Segoe UI", Tahoma, sans-serif',
            fontSize: 11,
          }}
        >
          <div style={{ display: "flex", minHeight: 160 }}>
            {/* Blue side bar with rotated text */}
            <div style={{
              width: 22,
              background: "linear-gradient(to top, #000080, #1084d0)",
              display: "flex",
              alignItems: "flex-end",
              justifyContent: "center",
              padding: "6px 0",
            }}>
              <span style={{
                writingMode: "vertical-rl",
                transform: "rotate(180deg)",
                color: "white",
                fontWeight: "bold",
                fontSize: 13,
                letterSpacing: 2,
              }}>
                panoramAI
              </span>
            </div>

            {/* Menu items */}
            <div style={{ flex: 1, padding: "4px 0" }}>
              <MenuItem
                icon="&#128187;"
                label="Mode normal"
                onClick={() => { setStartOpen(false); onToggle(); }}
              />
              <div style={{ borderTop: "1px solid #808080", borderBottom: "1px solid #fff", margin: "3px 6px" }} />
              <MenuItem
                icon="&#128196;"
                label="Vue d'ensemble"
                onClick={() => { setStartOpen(false); window.location.href = "/"; }}
              />
              <MenuItem
                icon="&#128202;"
                label="Concurrents"
                onClick={() => { setStartOpen(false); window.location.href = "/competitors"; }}
              />
              <MenuItem
                icon="&#128250;"
                label="Publicités"
                onClick={() => { setStartOpen(false); window.location.href = "/ads"; }}
              />
              <div style={{ borderTop: "1px solid #808080", borderBottom: "1px solid #fff", margin: "3px 6px" }} />
              <MenuItem
                icon="&#128683;"
                label="Arreter..."
                bold
                onClick={() => { setStartOpen(false); onToggle(); }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Taskbar */}
      <div
        style={{
          position: "fixed",
          bottom: 0,
          left: 0,
          right: 0,
          height: 30,
          zIndex: 99997,
          background: "#c0c0c0",
          borderTop: "2px solid #fff",
          boxShadow: "inset 0 1px 0 #dfdfdf",
          display: "flex",
          alignItems: "center",
          gap: 2,
          padding: "2px 2px",
          fontFamily: '"Segoe UI", Tahoma, sans-serif',
          fontSize: 11,
        }}
      >
        {/* Start button */}
        <button
          onClick={() => setStartOpen(!startOpen)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 3,
            padding: "1px 8px",
            height: 24,
            fontWeight: "bold",
            fontSize: 11,
            fontFamily: "inherit",
            background: "#c0c0c0",
            border: "none",
            cursor: "pointer",
            boxShadow: startOpen
              ? "inset 1px 1px 0 #0a0a0a, inset -1px -1px 0 #fff, inset 2px 2px 0 #808080"
              : "inset -1px -1px 0 #0a0a0a, inset 1px 1px 0 #fff, inset -2px -2px 0 #808080, inset 2px 2px 0 #dfdfdf",
          }}
        >
          <span style={{ fontSize: 13, lineHeight: 1 }}>&#127987;&#65039;</span>
          <span>Demarrer</span>
        </button>

        {/* Quick launch separator */}
        <div style={{ width: 1, height: 22, borderLeft: "1px solid #808080", borderRight: "1px solid #fff", margin: "0 3px" }} />

        {/* Active window button - sunken */}
        <div
          style={{
            flex: "0 0 200px",
            maxWidth: 200,
            height: 24,
            background: "#c0c0c0",
            boxShadow: "inset 1px 1px 0 #0a0a0a, inset -1px -1px 0 #fff",
            display: "flex",
            alignItems: "center",
            padding: "0 6px",
            fontWeight: "bold",
            overflow: "hidden",
            whiteSpace: "nowrap",
            textOverflow: "ellipsis",
            fontSize: 11,
          }}
        >
          <span style={{ marginRight: 4 }}>&#128202;</span>
          {pageTitle}
        </div>

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* System tray */}
        <div
          style={{
            height: 24,
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "0 8px 0 6px",
            boxShadow: "inset 1px 1px 0 #808080, inset -1px -1px 0 #fff",
            fontSize: 11,
          }}
        >
          <span title="Volume" style={{ fontSize: 12, cursor: "default" }}>&#128264;</span>
          <span style={{ fontVariantNumeric: "tabular-nums" }}>{time}</span>
        </div>
      </div>
    </>
  );
}

function MenuItem({ icon, label, onClick, bold }: { icon: string; label: string; onClick: () => void; bold?: boolean }) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        width: "100%",
        padding: "5px 10px",
        border: "none",
        background: hovered ? "#000080" : "transparent",
        color: hovered ? "#fff" : "#000",
        cursor: "pointer",
        fontSize: 11,
        fontWeight: bold ? "bold" : "normal",
        fontFamily: "inherit",
        textAlign: "left",
        boxShadow: "none",
        minHeight: "auto",
        outline: "none",
      }}
    >
      <span style={{ fontSize: 15, width: 20, textAlign: "center", flexShrink: 0 }} dangerouslySetInnerHTML={{ __html: icon }} />
      {label}
    </button>
  );
}
