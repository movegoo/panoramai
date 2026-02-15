"use client";

import { useEffect, useState, useCallback } from "react";

// Cheat code: up up down down left right left right B A B A
const CHEAT_SEQUENCE = [
  "ArrowUp", "ArrowUp",
  "ArrowDown", "ArrowDown",
  "ArrowLeft", "ArrowRight",
  "ArrowLeft", "ArrowRight",
  "b", "a",
  "b", "a",
];

const STORAGE_KEY = "win98_mode";

export function useWin98Mode() {
  const [active, setActive] = useState(false);
  const [inputIndex, setInputIndex] = useState(0);
  const [showBSOD, setShowBSOD] = useState(false);

  // Restore from localStorage on mount
  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "1") {
      setActive(true);
      document.documentElement.classList.add("win98");
    }
  }, []);

  const toggle = useCallback(() => {
    setActive((prev) => {
      const next = !prev;
      if (next) {
        // Activate: show BSOD first, then apply
        setShowBSOD(true);
        localStorage.setItem(STORAGE_KEY, "1");
        setTimeout(() => {
          document.documentElement.classList.add("win98");
          setShowBSOD(false);
        }, 2400);
      } else {
        localStorage.removeItem(STORAGE_KEY);
        document.documentElement.classList.remove("win98");
      }
      return next;
    });
  }, []);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      const expected = CHEAT_SEQUENCE[inputIndex];
      const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      if (key === expected) {
        const next = inputIndex + 1;
        if (next === CHEAT_SEQUENCE.length) {
          toggle();
          setInputIndex(0);
        } else {
          setInputIndex(next);
        }
      } else {
        // Reset on wrong key, but check if it's the start of the sequence
        setInputIndex(key === CHEAT_SEQUENCE[0] ? 1 : 0);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [inputIndex, toggle]);

  return { active, showBSOD, toggle };
}
