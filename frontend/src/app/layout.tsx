import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/lib/theme-context";

export const metadata: Metadata = {
  title: "Sistema Comerciante P2P — Mesa de Liquidez y Arbitraje Institucional",
  description:
    "Terminal institucional de arbitraje P2P en Binance, contabilidad SENIAT en partida doble y control de parada segura.",
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
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap"
          rel="stylesheet"
        />
        <script src="https://telegram.org/js/telegram-web-app.js" async />
      </head>
      <body
        suppressHydrationWarning
        className="bg-background text-on-surface antialiased selection:bg-[#f59e0b] selection:text-black min-h-screen flex flex-col"
      >
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
