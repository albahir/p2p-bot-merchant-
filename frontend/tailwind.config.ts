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
        primary: "#e2b870",
        "primary-container": "#c98b2c",
        "on-primary": "#140e04",
        "on-primary-container": "#140e04",
        secondary: "#86a8c6",
        "secondary-container": "#3b5873",
        "on-secondary": "#0b1520",
        tertiary: "#5ea88a",
        "tertiary-container": "#3a7860",
        "on-tertiary": "#061b13",
        error: "#d46a6a",
        "error-container": "#7f2323",
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
