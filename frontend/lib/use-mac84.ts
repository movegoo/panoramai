"use client";

import { useEffect, useState, useCallback } from "react";

// Cheat code: down down up up left right left right B A B A
const CHEAT_SEQUENCE = [
  "ArrowDown", "ArrowDown",
  "ArrowUp", "ArrowUp",
  "ArrowLeft", "ArrowRight",
  "ArrowLeft", "ArrowRight",
  "b", "a",
  "b", "a",
];

const STORAGE_KEY = "mac84_mode";

export function useMac84Mode() {
  const [active, setActive] = useState(false);
  const [inputIndex, setInputIndex] = useState(0);
  const [showBoot, setShowBoot] = useState(false);

  // Restore from localStorage on mount
  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "1") {
      setActive(true);
      document.documentElement.classList.add("mac84");
    }
  }, []);

  const toggle = useCallback(() => {
    setActive((prev) => {
      const next = !prev;
      if (next) {
        setShowBoot(true);
        localStorage.setItem(STORAGE_KEY, "1");
        setTimeout(() => {
          document.documentElement.classList.add("mac84");
          setShowBoot(false);
        }, 3000);
      } else {
        localStorage.removeItem(STORAGE_KEY);
        document.documentElement.classList.remove("mac84");
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
        setInputIndex(key === CHEAT_SEQUENCE[0] ? 1 : 0);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [inputIndex, toggle]);

  return { active, showBoot, toggle };
}
