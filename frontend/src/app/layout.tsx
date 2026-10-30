import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "P2P Crypto App // Arbitraje & Control Fiscal",
  description: "Terminal móvil y web de alta frecuencia para comercio P2P en Binance y control fiscal en Venezuela.",
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
      <body className="bg-[#050811] text-slate-100 min-h-screen flex flex-col font-sans">
        <main className="flex-1 w-full mx-auto py-4 sm:py-6 px-2 sm:px-4">
          {children}
        </main>
      </body>
    </html>
  );
}
