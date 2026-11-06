"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

export type Theme = "dark" | "dim";

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType>({
  theme: "dark",
  toggleTheme: () => {},
  setTheme: () => {},
});

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("dark");

  useEffect(() => {
    try {
      const saved = localStorage.getItem("p2p_theme");
      const initial: Theme = saved === "dim" ? "dim" : "dark";
      setThemeState(initial);
      applyTheme(initial);
    } catch {
      applyTheme("dark");
    }
  }, []);

  function applyTheme(t: Theme) {
    if (typeof document !== "undefined") {
      const root = document.documentElement;
      root.classList.remove("dark", "dim", "light");
      root.classList.add(t);
    }
  }

  function setTheme(t: Theme) {
    setThemeState(t);
    try {
      localStorage.setItem("p2p_theme", t);
    } catch {
      // Ignorar modo privado sin localStorage
    }
    applyTheme(t);
  }

  function toggleTheme() {
    setTheme(theme === "dark" ? "dim" : "dark");
  }

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
