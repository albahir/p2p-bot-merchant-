"use client";

import React from "react";
import { PerspectiveMode, usePerspective } from "@/lib/perspective-context";

interface PerspectiveToggleProps {
  onSelectMode?: (mode: PerspectiveMode) => void;
  compact?: boolean;
}

/**
 * Interruptor unificado de perspectiva operativa:
 * - MAKER (Por defecto): Comerciante Anunciante (publicas anuncios de compra/venta).
 * - TAKER: Cliente / Ejecución Directa (tomas anuncios existentes con 0% comisión Binance).
 */
export function PerspectiveToggle({ onSelectMode, compact = false }: PerspectiveToggleProps) {
  const { perspective, setPerspective } = usePerspective();

  function handleChange(next: PerspectiveMode) {
    setPerspective(next);
    if (onSelectMode) {
      onSelectMode(next);
    }
  }

  return (
    <div
      role="group"
      aria-label="Perspectiva operativa Maker o Taker"
      className="p-0.5 rounded-lg bg-surface-container-low border border-[#1e2430] inline-flex items-center text-[11px] font-mono shrink-0"
    >
      <button
        type="button"
        aria-pressed={perspective === "MAKER"}
        onClick={() => handleChange("MAKER")}
        title="Modo Comerciante Maker (Anunciante): muestra las tasas y márgenes donde tú publicas tus propios anuncios en Binance P2P"
        className={`px-2.5 py-1 rounded-md flex items-center gap-1 transition-colors cursor-pointer ${
          perspective === "MAKER"
            ? "bg-primary-container text-on-primary font-bold"
            : "text-slate-400 hover:text-white"
        }`}
      >
        <span className="material-symbols-outlined text-[14px]" aria-hidden="true">
          storefront
        </span>
        <span>{compact ? "Maker" : "Maker (Anuncio)"}</span>
      </button>
      <button
        type="button"
        aria-pressed={perspective === "TAKER"}
        onClick={() => handleChange("TAKER")}
        title="Modo Taker (Directo 0% fee): muestra las tasas y resultados al comprar o vender directamente tomando anuncios ya publicados"
        className={`px-2.5 py-1 rounded-md flex items-center gap-1 transition-colors cursor-pointer ${
          perspective === "TAKER"
            ? "bg-tertiary text-on-tertiary font-bold"
            : "text-slate-400 hover:text-white"
        }`}
      >
        <span className="material-symbols-outlined text-[14px]" aria-hidden="true">
          bolt
        </span>
        <span>{compact ? "Taker" : "Taker (Directo)"}</span>
      </button>
    </div>
  );
}
