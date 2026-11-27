"use client";

import React from "react";
import { canonicalBankName } from "@/lib/api";

interface BankLogoProps {
  bankName: string;
  size?: number;
  className?: string;
}

interface BankBrandVisual {
  label: string;
  bg: string;
  border: string;
  accent: string;
  textColor: string;
  glyph: "BDV" | "BANESCO" | "MERCANTIL" | "PAGOMOVIL" | "BBVA" | "BNC" | "BANCAMIGA" | "TESORO" | "BANPLUS" | "BANCARIBE" | "BFC" | "MONO";
  imageSrc?: string;
  imageBg?: string;
}

function resolveBrand(bankName: string): BankBrandVisual {
  const canon = canonicalBankName(bankName).toLowerCase();
  const rawLow = (bankName || "").toLowerCase();

  if (canon.includes("banesco") || rawLow.includes("banesco")) {
    return {
      label: "Banesco",
      bg: "#006937",
      border: "#10b981",
      accent: "#0096d6",
      textColor: "#ffffff",
      glyph: "BANESCO",
      imageSrc: "/banks/banesco.png",
      imageBg: "#ffffff",
    };
  }
  if (canon.includes("venezuela") || rawLow.includes("venezuela") || rawLow.includes("bdv") || rawLow.includes("specificbank")) {
    return {
      label: "Banco de Venezuela",
      bg: "#b91c1c",
      border: "#ef4444",
      accent: "#f8fafc",
      textColor: "#ffffff",
      glyph: "BDV",
      imageSrc: "/banks/venezuela.png",
      imageBg: "#ffffff",
    };
  }
  if (canon.includes("mercantil") || rawLow.includes("mercantil")) {
    return {
      label: "Mercantil",
      bg: "#0038a8",
      border: "#3b82f6",
      accent: "#ff6b00",
      textColor: "#ffffff",
      glyph: "MERCANTIL",
      imageSrc: "/banks/mercantil.png",
      imageBg: "#0038a8",
    };
  }
  if (canon.includes("pago móvil") || rawLow.includes("pago móvil") || rawLow.includes("pagomovil") || rawLow.includes("pago movil")) {
    return {
      label: "Pago Móvil",
      bg: "#0f766e",
      border: "#2dd4bf",
      accent: "#f59e0b",
      textColor: "#ffffff",
      glyph: "PAGOMOVIL",
    };
  }
  if (canon.includes("provincial") || rawLow.includes("bbva") || rawLow.includes("provincial")) {
    return {
      label: "BBVA Provincial",
      bg: "#004481",
      border: "#60a5fa",
      accent: "#2dcccd",
      textColor: "#ffffff",
      glyph: "BBVA",
      imageSrc: "/banks/provincial.png",
      imageBg: "#004481",
    };
  }
  if (canon === "bnc" || rawLow.includes("bnc") || rawLow.includes("nacional de cr")) {
    return {
      label: "BNC",
      bg: "#0055a5",
      border: "#38bdf8",
      accent: "#e11d48",
      textColor: "#ffffff",
      glyph: "BNC",
      imageSrc: "/banks/bnc.png",
      imageBg: "#ffffff",
    };
  }
  if (canon.includes("bancamiga") || rawLow.includes("bancamiga")) {
    return {
      label: "Bancamiga",
      bg: "#0066b2",
      border: "#38bdf8",
      accent: "#84cc16",
      textColor: "#ffffff",
      glyph: "BANCAMIGA",
      imageSrc: "/banks/bancamiga.png",
      imageBg: "#0066b2",
    };
  }
  if (canon.includes("tesoro") || rawLow.includes("tesoro")) {
    return {
      label: "Banco del Tesoro",
      bg: "#1e3a8a",
      border: "#fbbf24",
      accent: "#f59e0b",
      textColor: "#ffffff",
      glyph: "TESORO",
      imageSrc: "/banks/bancodeltesoro.png",
      imageBg: "#ffffff",
    };
  }
  if (canon.includes("banplus") || rawLow.includes("banplus")) {
    return {
      label: "Banplus",
      bg: "#007a3d",
      border: "#34d399",
      accent: "#fde047",
      textColor: "#ffffff",
      glyph: "BANPLUS",
      imageSrc: "/banks/banplus.png",
      imageBg: "#ffffff",
    };
  }
  if (canon.includes("bancaribe") || rawLow.includes("bancaribe")) {
    return {
      label: "Bancaribe",
      bg: "#0e7490",
      border: "#22d3ee",
      accent: "#facc15",
      textColor: "#ffffff",
      glyph: "BANCARIBE",
      imageSrc: "/banks/bancaribe.png",
      imageBg: "#0e7490",
    };
  }
  if (canon === "bfc" || rawLow.includes("fondo com")) {
    return {
      label: "BFC",
      bg: "#991b1b",
      border: "#f87171",
      accent: "#38bdf8",
      textColor: "#ffffff",
      glyph: "BFC",
    };
  }
  if (rawLow.includes("activo")) {
    return {
      label: "Activo",
      bg: "#c2410c",
      border: "#fb923c",
      accent: "#fef08a",
      textColor: "#ffffff",
      glyph: "MONO",
    };
  }
  if (rawLow.includes("plaza")) {
    return {
      label: "Plaza",
      bg: "#0369a1",
      border: "#38bdf8",
      accent: "#bae6fd",
      textColor: "#ffffff",
      glyph: "MONO",
    };
  }
  if (rawLow.includes("venezolano de cr")) {
    return {
      label: "BVC",
      bg: "#7f1d1d",
      border: "#fca5a5",
      accent: "#f59e0b",
      textColor: "#ffffff",
      glyph: "MONO",
    };
  }
  if (rawLow.includes("r4")) {
    return {
      label: "R4",
      bg: "#4338ca",
      border: "#818cf8",
      accent: "#c7d2fe",
      textColor: "#ffffff",
      glyph: "MONO",
    };
  }
  if (rawLow.includes("n58")) {
    return {
      label: "N58",
      bg: "#115e59",
      border: "#2dd4bf",
      accent: "#99f6e4",
      textColor: "#ffffff",
      glyph: "MONO",
    };
  }
  const cleanShort = (bankName || "BK").replace(/[^A-Za-z0-9]/g, "").slice(0, 3).toUpperCase() || "BK";
  return {
    label: cleanShort,
    bg: "#1e293b",
    border: "#475569",
    accent: "#f59e0b",
    textColor: "#e2e8f0",
    glyph: "MONO",
  };
}

/**
 * Logos oficiales locales de la banca venezolana en /banks/*.png con fallback SVG vectorial.
 */
export function BankLogo({ bankName, size = 28, className = "" }: BankLogoProps) {
  const brand = resolveBrand(bankName);

  if (brand.imageSrc) {
    const isLightBg = brand.imageBg === "#ffffff";
    return (
      <span
        title={brand.label}
        className={`inline-flex items-center justify-center shrink-0 rounded-md overflow-hidden select-none ${isLightBg ? "p-[2px]" : ""} ${className}`}
        style={{
          width: size,
          height: size,
          backgroundColor: brand.imageBg ?? brand.bg,
          border: `1px solid ${brand.border}55`,
        }}
        aria-hidden="true"
      >
        <img
          src={brand.imageSrc}
          alt={brand.label}
          width={size}
          height={size}
          className="w-full h-full object-contain"
          loading="lazy"
          decoding="async"
        />
      </span>
    );
  }

  return (
    <span
      title={brand.label}
      className={`inline-flex items-center justify-center shrink-0 rounded-md overflow-hidden select-none ${className}`}
      style={{
        width: size,
        height: size,
        backgroundColor: brand.bg,
        border: `1px solid ${brand.border}55`,
      }}
      aria-hidden="true"
    >
      <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
        {brand.glyph === "BANESCO" && (
          <>
            <path d="M5 24C10 19 20 19 27 24" stroke="#00a8e8" strokeWidth="2.5" strokeLinecap="round" />
            <path d="M7 10H17C19.5 10 21 11.3 21 13.3C21 14.8 19.9 15.8 18.6 16.1C20.2 16.4 21.5 17.6 21.5 19.3C21.5 21.5 19.8 22.8 17 22.8H7V10Z" fill="#ffffff" fillOpacity="0.16" />
            <text x="16" y="18.5" textAnchor="middle" fill="#ffffff" fontSize="11" fontWeight="800" fontFamily="system-ui, sans-serif">
              B
            </text>
            <circle cx="24" cy="9" r="2.5" fill="#ef4444" />
          </>
        )}

        {brand.glyph === "BDV" && (
          <>
            <path d="M6 23L16 7L26 23H6Z" fill="#ffffff" fillOpacity="0.14" stroke="#ffffff" strokeWidth="1.4" strokeLinejoin="round" />
            <text x="16" y="21.5" textAnchor="middle" fill="#ffffff" fontSize="8.5" fontWeight="900" fontFamily="system-ui, sans-serif">
              BDV
            </text>
          </>
        )}

        {brand.glyph === "MERCANTIL" && (
          <>
            <circle cx="23.5" cy="8.5" r="3.2" fill={brand.accent} />
            <path d="M7 22V11L12.5 17.5L18 11V22" stroke="#ffffff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          </>
        )}

        {brand.glyph === "PAGOMOVIL" && (
          <>
            <rect x="9.5" y="5.5" width="13" height="21" rx="2.6" stroke="#ffffff" strokeWidth="2" fill="#ffffff" fillOpacity="0.1" />
            <path d="M13 13.5H20.5M20.5 13.5L18 11M20.5 13.5L18 16" stroke={brand.accent} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M19 18.5H11.5M11.5 18.5L14 16M11.5 18.5L14 21" stroke="#ffffff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </>
        )}

        {brand.glyph === "BBVA" && (
          <>
            <text x="16" y="19" textAnchor="middle" fill="#ffffff" fontSize="9.2" fontWeight="800" fontFamily="system-ui, sans-serif" letterSpacing="-0.5">
              BBVA
            </text>
            <rect x="7" y="22.5" width="18" height="2" rx="1" fill={brand.accent} />
          </>
        )}

        {brand.glyph === "BNC" && (
          <>
            <path d="M4 23H28" stroke={brand.accent} strokeWidth="2.6" strokeLinecap="round" />
            <text x="16" y="18.5" textAnchor="middle" fill="#ffffff" fontSize="9.5" fontWeight="900" fontFamily="system-ui, sans-serif">
              BNC
            </text>
          </>
        )}

        {brand.glyph === "BANCAMIGA" && (
          <>
            <circle cx="11" cy="11" r="2.2" fill={brand.accent} />
            <path d="M7 21C11 14 20 13 25 19" stroke={brand.accent} strokeWidth="2.4" strokeLinecap="round" />
            <text x="18" y="15" textAnchor="middle" fill="#ffffff" fontSize="9.5" fontWeight="800" fontFamily="system-ui, sans-serif">
              BA
            </text>
          </>
        )}

        {brand.glyph === "TESORO" && (
          <>
            <rect x="7" y="9" width="18" height="14" rx="2" stroke={brand.accent} strokeWidth="1.8" fill="#ffffff" fillOpacity="0.08" />
            <text x="16" y="19.5" textAnchor="middle" fill="#fef08a" fontSize="9.5" fontWeight="800" fontFamily="system-ui, sans-serif">
              BT
            </text>
          </>
        )}

        {brand.glyph === "BANPLUS" && (
          <>
            <path d="M16 7V25M7 16H25" stroke={brand.accent} strokeWidth="3.2" strokeLinecap="round" strokeOpacity="0.35" />
            <text x="16" y="19.5" textAnchor="middle" fill="#ffffff" fontSize="10" fontWeight="900" fontFamily="system-ui, sans-serif">
              B+
            </text>
          </>
        )}

        {brand.glyph === "BANCARIBE" && (
          <>
            <circle cx="22.5" cy="9.5" r="2.8" fill={brand.accent} />
            <path d="M6 21C10 18.5 14 23 19 20.5C22 19 24.5 19.5 26 21" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
            <text x="13" y="17" textAnchor="middle" fill="#ffffff" fontSize="9.5" fontWeight="800" fontFamily="system-ui, sans-serif">
              BC
            </text>
          </>
        )}

        {brand.glyph === "BFC" && (
          <>
            <rect x="5" y="22.5" width="22" height="2.2" rx="1" fill={brand.accent} />
            <text x="16" y="18.5" textAnchor="middle" fill="#ffffff" fontSize="9.5" fontWeight="900" fontFamily="system-ui, sans-serif">
              BFC
            </text>
          </>
        )}

        {brand.glyph === "MONO" && (
          <>
            <circle cx="24" cy="8" r="2" fill={brand.accent} />
            <text x="16" y="19.5" textAnchor="middle" fill={brand.textColor} fontSize="9.5" fontWeight="800" fontFamily="system-ui, sans-serif">
              {brand.label.slice(0, 3).toUpperCase()}
            </text>
          </>
        )}
      </svg>
    </span>
  );
}
