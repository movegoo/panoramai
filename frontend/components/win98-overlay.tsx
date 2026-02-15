"use client";

import { useEffect, useState } from "react";

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
        color: "#fff",
        fontFamily: '"Fixedsys", "Courier New", monospace',
        fontSize: "14px",
        lineHeight: 1.6,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "40px",
        cursor: "none",
      }}
    >
      <div style={{ maxWidth: 650, textAlign: "center" }}>
        {showText >= 1 && (
          <div style={{ background: "#aaa", color: "#0000aa", display: "inline-block", padding: "0 8px", marginBottom: 24, fontWeight: "bold" }}>
            panoramAI Windows 98 Edition
          </div>
        )}

        {showText >= 1 && (
          <p style={{ marginTop: 16, textAlign: "left" }}>
            A fatal exception 0E has occurred at 0028:C0034B03 in VXD PANORAMAI(01) + 00001B03. The current application will be terminated.
          </p>
        )}

        {showText >= 2 && (
          <p style={{ marginTop: 16, textAlign: "left" }}>
            * The design system has been corrupted. Loading Windows 98 UI...<br />
            * Replacing rounded corners with sharp edges... OK<br />
            * Downgrading gradients to flat gray... OK<br />
            * Installing Comic Sans... SKIPPED (we have standards)
          </p>
        )}

        {showText >= 3 && (
          <p style={{ marginTop: 16, textAlign: "left" }}>
            * Applying PostHog hedgehog energy... OK<br />
            * Setting background to Teal... OK
          </p>
        )}

        {showText >= 4 && (
          <p style={{ marginTop: 24, textAlign: "center" }}>
            Press any key to continue _<span style={{ animation: "blink 1s steps(1) infinite" }}>|</span>
          </p>
        )}
      </div>

      <style>{`
        @keyframes blink {
          0%, 49% { opacity: 1; }
          50%, 100% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}

export function Win98Taskbar({ active, onToggle }: { active: boolean; onToggle: () => void }) {
  const [time, setTime] = useState("");
  const [startOpen, setStartOpen] = useState(false);

  useEffect(() => {
    function tick() {
      const now = new Date();
      setTime(now.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }));
    }
    tick();
    const i = setInterval(tick, 30000);
    return () => clearInterval(i);
  }, []);

  if (!active) return null;

  return (
    <>
      {/* Start menu */}
      {startOpen && (
        <div
          style={{
            position: "fixed",
            bottom: 28,
            left: 0,
            width: 180,
            zIndex: 99998,
            background: "#c0c0c0",
            boxShadow: "inset -1px -1px 0 #0a0a0a, inset 1px 1px 0 #fff, inset -2px -2px 0 #808080, inset 2px 2px 0 #dfdfdf",
            fontFamily: '"MS Sans Serif", Tahoma, sans-serif',
            fontSize: 11,
          }}
        >
          {/* Blue side bar */}
          <div style={{ display: "flex" }}>
            <div style={{ width: 24, background: "linear-gradient(to top, #000080, #1084d0)", writingMode: "vertical-rl", textOrientation: "mixed", color: "white", fontWeight: "bold", fontSize: 14, padding: "8px 2px", letterSpacing: 2 }}>
              panoramAI
            </div>
            <div style={{ flex: 1 }}>
              <button
                onClick={() => { setStartOpen(false); window.open("https://posthog.com", "_blank"); }}
                style={{
                  display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "6px 8px", border: "none", background: "transparent", cursor: "pointer", fontSize: 11, fontFamily: "inherit", textAlign: "left",
                }}
                onMouseEnter={(e) => { (e.target as HTMLElement).style.background = "#000080"; (e.target as HTMLElement).style.color = "#fff"; }}
                onMouseLeave={(e) => { (e.target as HTMLElement).style.background = "transparent"; (e.target as HTMLElement).style.color = "#000"; }}
              >
                <span style={{ fontSize: 16 }}>&#128024;</span> PostHog
              </button>
              <button
                onClick={() => { setStartOpen(false); onToggle(); }}
                style={{
                  display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "6px 8px", border: "none", background: "transparent", cursor: "pointer", fontSize: 11, fontFamily: "inherit", textAlign: "left",
                }}
                onMouseEnter={(e) => { (e.target as HTMLElement).style.background = "#000080"; (e.target as HTMLElement).style.color = "#fff"; }}
                onMouseLeave={(e) => { (e.target as HTMLElement).style.background = "transparent"; (e.target as HTMLElement).style.color = "#000"; }}
              >
                <span style={{ fontSize: 16 }}>&#128187;</span> Mode normal
              </button>
              <div style={{ borderTop: "1px solid #808080", borderBottom: "1px solid #fff", margin: "2px 4px" }} />
              <button
                onClick={() => { setStartOpen(false); onToggle(); }}
                style={{
                  display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "6px 8px", border: "none", background: "transparent", cursor: "pointer", fontSize: 11, fontFamily: "inherit", textAlign: "left",
                }}
                onMouseEnter={(e) => { (e.target as HTMLElement).style.background = "#000080"; (e.target as HTMLElement).style.color = "#fff"; }}
                onMouseLeave={(e) => { (e.target as HTMLElement).style.background = "transparent"; (e.target as HTMLElement).style.color = "#000"; }}
              >
                <span style={{ fontSize: 16 }}>&#128683;</span> Arreter...
              </button>
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
          height: 28,
          zIndex: 99997,
          background: "#c0c0c0",
          borderTop: "2px solid #fff",
          display: "flex",
          alignItems: "center",
          gap: 2,
          padding: "0 2px",
          fontFamily: '"MS Sans Serif", Tahoma, sans-serif',
          fontSize: 11,
        }}
      >
        {/* Start button */}
        <button
          onClick={() => setStartOpen(!startOpen)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            padding: "1px 6px",
            height: 22,
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
          <span style={{ fontSize: 14 }}>&#127987;&#65039;</span>
          Demarrer
        </button>

        {/* Quick launch separator */}
        <div style={{ width: 1, height: 20, borderLeft: "1px solid #808080", borderRight: "1px solid #fff", margin: "0 2px" }} />

        {/* Active window */}
        <div
          style={{
            flex: "0 0 180px",
            height: 22,
            background: "#c0c0c0",
            boxShadow: "inset 1px 1px 0 #0a0a0a, inset -1px -1px 0 #fff",
            display: "flex",
            alignItems: "center",
            padding: "0 6px",
            fontWeight: "bold",
            overflow: "hidden",
            whiteSpace: "nowrap",
            textOverflow: "ellipsis",
          }}
        >
          &#128202; panoramAI - Veille
        </div>

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* System tray */}
        <div
          style={{
            height: 22,
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "0 8px",
            boxShadow: "inset 1px 1px 0 #808080, inset -1px -1px 0 #fff",
            fontSize: 11,
          }}
        >
          <span title="Volume">&#128266;</span>
          <span>{time}</span>
        </div>
      </div>
    </>
  );
}
