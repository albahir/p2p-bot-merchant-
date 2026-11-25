"use client";

import React, { useId } from "react";
import { MerchantTier } from "@/lib/p2p-calculator";

interface BinanceTierBadgeProps {
  tier: MerchantTier;
  size?: number;
  className?: string;
}

/**
 * Insignias vectoriales inspiradas en el Programa VIP de Comerciantes Verificados de Binance P2P
 * (Estándar, Bronce, Plata, Oro y Manual).
 */
export function BinanceTierBadge({
  tier,
  size = 24,
  className = "",
}: BinanceTierBadgeProps) {
  const uid = useId().replace(/:/g, "");

  if (tier === "CUSTOM") {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 28 28"
        fill="none"
        aria-hidden="true"
        className={className}
      >
        <defs>
          <linearGradient id={`cust-${uid}`} x1="4" y1="3" x2="24" y2="25" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#67e8f9" />
            <stop offset="100%" stopColor="#0284c7" />
          </linearGradient>
        </defs>
        <path
          d="M14 2.5L24.2 8.4V19.6L14 25.5L3.8 19.6V8.4L14 2.5Z"
          fill={`url(#cust-${uid})`}
          fillOpacity="0.18"
          stroke={`url(#cust-${uid})`}
          strokeWidth="1.75"
        />
        <line x1="9" y1="11" x2="19" y2="11" stroke="#67e8f9" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="12" cy="11" r="1.8" fill="#0a0e13" stroke="#67e8f9" strokeWidth="1.5" />
        <line x1="9" y1="17" x2="19" y2="17" stroke="#67e8f9" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="16.5" cy="17" r="1.8" fill="#0a0e13" stroke="#67e8f9" strokeWidth="1.5" />
      </svg>
    );
  }

  if (tier === "STANDARD") {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 28 28"
        fill="none"
        aria-hidden="true"
        className={className}
      >
        <path
          d="M14 2.5L23.5 6.8V13.8C23.5 19.6 19.4 23.8 14 25.6C8.6 23.8 4.5 19.6 4.5 13.8V6.8L14 2.5Z"
          fill="#1e293b"
          stroke="#94a3b8"
          strokeWidth="1.6"
        />
        <path
          d="M14 8.5L18.5 13L14 17.5L9.5 13L14 8.5Z"
          stroke="#cbd5e1"
          strokeWidth="1.5"
          fill="#475569"
          fillOpacity="0.35"
        />
      </svg>
    );
  }

  // Paletas metálicas estilo Binance Verified Merchant (Bronce, Plata, Oro)
  const palettes: Record<
    "BRONZE" | "SILVER" | "GOLD",
    {
      top: string;
      mid: string;
      bot: string;
      stroke: string;
      check: string;
      sparkle?: boolean;
    }
  > = {
    BRONZE: {
      top: "#f3b178",
      mid: "#cd7f32",
      bot: "#7c3f12",
      stroke: "#fbd3a8",
      check: "#fff7ed",
    },
    SILVER: {
      top: "#f8fafc",
      mid: "#cbd5e1",
      bot: "#64748b",
      stroke: "#ffffff",
      check: "#0f172a",
    },
    GOLD: {
      top: "#fef08a",
      mid: "#fcd535",
      bot: "#b45309",
      stroke: "#fef9c3",
      check: "#181a20",
      sparkle: true,
    },
  };

  const p = palettes[tier];

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 28 28"
      fill="none"
      aria-hidden="true"
      className={className}
    >
      <defs>
        <linearGradient id={`grad-${tier}-${uid}`} x1="4" y1="2" x2="24" y2="26" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor={p.top} />
          <stop offset="52%" stopColor={p.mid} />
          <stop offset="100%" stopColor={p.bot} />
        </linearGradient>
      </defs>
      {/* Escudo / Emblema Diamante Verificado estilo Binance P2P */}
      <path
        d="M14 2L24 6.4V13.8C24 19.9 19.7 24.2 14 26C8.3 24.2 4 19.9 4 13.8V6.4L14 2Z"
        fill={`url(#grad-${tier}-${uid})`}
        stroke={p.stroke}
        strokeWidth="1.2"
      />
      {/* Faceta interior estilo insignia Binance */}
      <path
        d="M14 4.8L21.3 8.1V13.6C21.3 18.2 18.2 21.5 14 23C9.8 21.5 6.7 18.2 6.7 13.6V8.1L14 4.8Z"
        fill="black"
        fillOpacity="0.12"
      />
      {/* Checkmark verificado */}
      <path
        d="M10.2 14.2L12.9 16.9L18.2 11.2"
        stroke={p.check}
        strokeWidth="2.35"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {p.sparkle && (
        <path
          d="M22.5 3.2L23.2 4.8L24.8 5.5L23.2 6.2L22.5 7.8L21.8 6.2L20.2 5.5L21.8 4.8L22.5 3.2Z"
          fill="#fef08a"
        />
      )}
    </svg>
  );
}
