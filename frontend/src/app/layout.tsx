import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/lib/theme-context";

export const metadata: Metadata = {
  title: "P2P Merchant Workstation // Arbitraje & Control Fiscal",
  description: "Terminal web y móvil de alta frecuencia para comercio P2P en Binance y control fiscal en Venezuela.",
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
      <body className="bg-[#F8F9FA] dark:bg-[#07090E] text-slate-900 dark:text-slate-100 min-h-screen flex flex-col font-sans transition-colors duration-150">
        <ThemeProvider>
          <main className="flex-1 w-full mx-auto py-3 sm:py-5 px-2 sm:px-4">
            {children}
          </main>
        </ThemeProvider>
      </body>
    </html>
  );
}
