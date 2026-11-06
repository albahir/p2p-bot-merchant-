import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--bg-canvas)",
        surface: "var(--bg-surface)",
        "surface-dim": "#101419",
        "surface-bright": "#36393f",
        "surface-container-lowest": "var(--bg-lowest)",
        "surface-container-low": "var(--bg-low)",
        "surface-container": "var(--bg-container)",
        "surface-container-high": "var(--bg-high)",
        "surface-container-highest": "#31353b",
        "on-surface": "#e0e2ea",
        "on-surface-variant": "#94a3b8",
        outline: "#64748b",
        "outline-variant": "#1e2430",
        primary: "#ffc174",
        "primary-container": "#f59e0b",
        "on-primary": "#1a1000",
        "on-primary-container": "#1a1000",
        secondary: "#4cd7f6",
        "secondary-container": "#03b5d3",
        "on-secondary": "#003640",
        tertiary: "#10b981",
        "tertiary-container": "#059669",
        "on-tertiary": "#002113",
        error: "#ef4444",
        "error-container": "#7f1d1d",
        "on-error": "#ffffff",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
        mono: ["JetBrains Mono", "Courier New", "monospace"],
      },
      spacing: {
        "space-xs": "0.25rem",
        "space-sm": "0.5rem",
        "space-md": "0.75rem",
        "space-lg": "1rem",
        "space-xl": "1.5rem",
      },
    },
  },
  plugins: [],
};

export default config;
