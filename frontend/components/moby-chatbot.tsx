"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { X, Send, ChevronDown, Code } from "lucide-react";
import { mobyAPI } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  sql?: string | null;
}

interface MobyConfig {
  enabled: boolean;
  position: string;
}

const POSITION_CLASSES: Record<string, string> = {
  "bottom-right": "bottom-5 right-5",
  "bottom-left": "bottom-5 left-5",
  "top-right": "top-5 right-5",
  "top-left": "top-5 left-5",
};

const PANEL_POSITION_CLASSES: Record<string, string> = {
  "bottom-right": "bottom-20 right-5",
  "bottom-left": "bottom-20 left-5",
  "top-right": "top-20 right-5",
  "top-left": "top-20 left-5",
};

const SUGGESTIONS = [
  "Combien de pubs actives a chaque concurrent ?",
  "Compare les followers Instagram de tous les concurrents",
  "Quelles pubs ont un score créatif > 80 ?",
];

export function MobyChatbot() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [config, setConfig] = useState<MobyConfig>({ enabled: true, position: "bottom-right" });
  const [showPulse, setShowPulse] = useState(true);
  const [expandedSql, setExpandedSql] = useState<Set<number>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    mobyAPI.getConfig().then(setConfig).catch(() => {});
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setShowPulse(false), 6000);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;

    const userMsg: Message = { role: "user", content: text.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const result = await mobyAPI.ask(text.trim(), history);
      const assistantMsg: Message = {
        role: "assistant",
        content: result.answer,
        sql: result.sql,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Désolé, une erreur est survenue. Réessayez." },
      ]);
    } finally {
      setLoading(false);
    }
  }, [loading, messages]);

  const toggleSql = (index: number) => {
    setExpandedSql((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  if (!config.enabled) return null;

  const posClass = POSITION_CLASSES[config.position] || POSITION_CLASSES["bottom-right"];
  const panelClass = PANEL_POSITION_CLASSES[config.position] || PANEL_POSITION_CLASSES["bottom-right"];

  return (
    <div className="fixed z-50" style={{ pointerEvents: "none" }}>
      {/* Chat Panel */}
      {open && (
        <div
          className={`fixed ${panelClass} w-[380px] h-[520px] bg-card border border-border rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-bottom-4 duration-300`}
          style={{ pointerEvents: "auto" }}
        >
          {/* Header */}
          <div className="flex items-center gap-3 px-4 py-3 bg-gradient-to-r from-violet-600 to-indigo-600 text-white shrink-0">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/20">
              <span className="text-lg">🐋</span>
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-sm leading-none">Moby</h3>
              <p className="text-[10px] text-white/70 mt-0.5">Assistant IA</p>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="flex h-7 w-7 items-center justify-center rounded-full hover:bg-white/20 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {messages.length === 0 && !loading && (
              <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
                <span className="text-4xl">🐋</span>
                <div>
                  <p className="text-sm font-medium text-foreground">Bonjour ! Je suis Moby</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Posez-moi vos questions sur les données concurrentielles
                  </p>
                </div>
                <div className="flex flex-col gap-2 w-full">
                  {SUGGESTIONS.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => sendMessage(s)}
                      className="text-left text-xs px-3 py-2 rounded-lg border border-border hover:bg-muted hover:border-violet-300 transition-colors text-muted-foreground"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm ${
                    msg.role === "user"
                      ? "bg-violet-600 text-white rounded-br-md"
                      : "bg-muted text-foreground rounded-bl-md"
                  }`}
                >
                  <div className="whitespace-pre-wrap break-words text-[13px] leading-relaxed">
                    {msg.content}
                  </div>
                  {msg.sql && msg.role === "assistant" && (
                    <div className="mt-2">
                      <button
                        onClick={() => toggleSql(i)}
                        className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <Code className="h-3 w-3" />
                        {expandedSql.has(i) ? "Masquer" : "Voir"} le SQL
                        <ChevronDown
                          className={`h-3 w-3 transition-transform ${expandedSql.has(i) ? "rotate-180" : ""}`}
                        />
                      </button>
                      {expandedSql.has(i) && (
                        <pre className="mt-1.5 p-2 bg-background/80 rounded-lg text-[10px] text-muted-foreground overflow-x-auto font-mono leading-relaxed">
                          {msg.sql}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-muted rounded-2xl rounded-bl-md px-4 py-3">
                  <div className="flex gap-1.5">
                    <span className="h-2 w-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="h-2 w-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="h-2 w-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="shrink-0 px-3 py-3 border-t border-border bg-card">
            <div className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Posez votre question..."
                rows={1}
                className="flex-1 resize-none bg-muted rounded-xl px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50 max-h-[80px] overflow-y-auto"
                style={{ minHeight: "40px" }}
              />
              <button
                onClick={() => sendMessage(input)}
                disabled={!input.trim() || loading}
                className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bubble */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className={`fixed ${posClass} group`}
          style={{ pointerEvents: "auto" }}
        >
          <div className="relative">
            {showPulse && (
              <div className="absolute inset-0 rounded-full bg-violet-500/30 animate-ping" />
            )}
            <div className="relative flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-violet-600 to-indigo-600 shadow-lg shadow-violet-500/25 hover:shadow-violet-500/40 hover:scale-110 transition-all duration-200 cursor-pointer">
              <span className="text-2xl">🐋</span>
            </div>
          </div>
        </button>
      )}
    </div>
  );
}
