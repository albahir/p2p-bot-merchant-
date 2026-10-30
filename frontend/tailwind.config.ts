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
        background: "#090d16",
        surface: "#0e1524",
        "surface-card": "#131c2e",
        "surface-elevated": "#1a253c",
        border: "#1e293b",
        "border-bright": "#2d3d59",
        brand: {
          red: "#e11d48",
          darkRed: "#9f1239",
          coral: "#f43f5e",
          lightRed: "#ffe4e6",
        },
        neon: {
          emerald: "#10b981",
          cyan: "#06b6d4",
          ruby: "#f43f5e",
          amber: "#f59e0b",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Courier New", "monospace"],
        sans: ["Geist", "Inter", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
