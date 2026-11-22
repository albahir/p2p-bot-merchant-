import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/lib/theme-context";
import { TelemetryProvider } from "@/lib/telemetry-context";

export const metadata: Metadata = {
  title: "Comerciante P2P — Binance & Contabilidad",
  description: "Arbitraje P2P en vivo, órdenes, conciliación bancaria y Google Sheets.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className="dark" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap"
          rel="stylesheet"
        />
        <script src="https://telegram.org/js/telegram-web-app.js" defer />
      </head>
      <body
        suppressHydrationWarning
        className="bg-background text-on-surface antialiased selection:bg-[#f59e0b] selection:text-black min-h-screen flex flex-col"
      >
        <ThemeProvider>
          <TelemetryProvider>{children}</TelemetryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
