import type { Metadata } from "next";
import "./globals.css";
import { TerminalHeader } from "@/components/terminal-header";
import { TelegramMiniAppBar } from "@/components/telegram-mini-app-bar";

export const metadata: Metadata = {
  title: "P2P Merchant Monitor // Arbitrage & Fiscal Terminal",
  description: "Terminal de alta frecuencia para comercio P2P en Binance y control fiscal en Venezuela.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
        <script src="https://telegram.org/js/telegram-web-app.js" async />
      </head>
      <body className="bg-background text-slate-100 min-h-screen flex flex-col font-sans pb-16 md:pb-0">
        <TerminalHeader />
        <main className="flex-1 max-w-7xl w-full mx-auto p-4 lg:p-8">
          {children}
        </main>
        <TelegramMiniAppBar />
      </body>
    </html>
  );
}
