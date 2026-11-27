"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

export type PerspectiveMode = "MAKER" | "TAKER";

interface PerspectiveContextType {
  perspective: PerspectiveMode;
  isMaker: boolean;
  setPerspective: (mode: PerspectiveMode) => void;
  togglePerspective: () => void;
}

const STORAGE_PERSPECTIVE_KEY = "p2p_perspective_mode";

const PerspectiveContext = createContext<PerspectiveContextType>({
  perspective: "MAKER",
  isMaker: true,
  setPerspective: () => {},
  togglePerspective: () => {},
});

export function PerspectiveProvider({ children }: { children: React.ReactNode }) {
  // Por defecto arranca siempre en MAKER (Comerciante con Anuncio)
  const [perspective, setPerspectiveState] = useState<PerspectiveMode>("MAKER");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_PERSPECTIVE_KEY);
      if (saved === "TAKER" || saved === "MAKER") {
        setPerspectiveState(saved);
      }
    } catch {
      // Ignorar modo privado sin localStorage
    }
  }, []);

  function setPerspective(mode: PerspectiveMode) {
    setPerspectiveState(mode);
    try {
      localStorage.setItem(STORAGE_PERSPECTIVE_KEY, mode);
    } catch {
      // Ignorar errores de almacenamiento
    }
  }

  function togglePerspective() {
    setPerspective(perspective === "MAKER" ? "TAKER" : "MAKER");
  }

  return (
    <PerspectiveContext.Provider
      value={{
        perspective,
        isMaker: perspective === "MAKER",
        setPerspective,
        togglePerspective,
      }}
    >
      {children}
    </PerspectiveContext.Provider>
  );
}

export function usePerspective() {
  return useContext(PerspectiveContext);
}
