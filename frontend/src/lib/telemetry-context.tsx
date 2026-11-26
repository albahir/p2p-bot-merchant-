"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  BCVRates,
  BinanceStatusResponse,
  BotStatus,
  User,
  apiRequest,
  getCurrentUser,
  getSheetsSettings,
  loginTelegramWebApp,
  warmAuthenticatedSession,
} from "@/lib/api";
import { useWebSocket } from "@/lib/useWebSocket";

interface TelemetryContextValue {
  user: User | null;
  bcv: BCVRates | null;
  botStatus: BotStatus | null;
  binanceStatus: BinanceStatusResponse | null;
  wsConnected: boolean;
  setBotStatus: React.Dispatch<React.SetStateAction<BotStatus | null>>;
  refreshTelemetry: (fresh?: boolean) => Promise<void>;
}

const TelemetryContext = createContext<TelemetryContextValue>({
  user: null,
  bcv: null,
  botStatus: null,
  binanceStatus: null,
  wsConnected: false,
  setBotStatus: () => {},
  refreshTelemetry: async () => {},
});

export function TelemetryProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [bcv, setBcv] = useState<BCVRates | null>(null);
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [binanceStatus, setBinanceStatus] = useState<BinanceStatusResponse | null>(null);

  const refreshTelemetry = useCallback(async (fresh = false) => {
    const currentUser = getCurrentUser();
    setUser(currentUser);

    const priority = fresh ? "high" : "low";
    const jobs: Promise<void>[] = [
      apiRequest<BCVRates>("/api/spreads/bcv", { fresh, cacheTtlMs: 5 * 60_000, priority })
        .then((rates) => setBcv(rates))
        .catch(() => {}),
    ];

    if (currentUser) {
      jobs.push(
        apiRequest<BotStatus>("/api/bot/status", { fresh, cacheTtlMs: 30_000, priority })
          .then((status) => setBotStatus(status))
          .catch(() => setUser(getCurrentUser()))
      );
    } else {
      setBotStatus(null);
    }

    if (currentUser && (currentUser.role === "ADMIN" || currentUser.role === "TRADER")) {
      jobs.push(
        apiRequest<BinanceStatusResponse>("/api/settings/binance", {
          fresh,
          cacheTtlMs: 45_000,
          priority,
        })
          .then((binance) => setBinanceStatus(binance))
          .catch(() => {}),
        getSheetsSettings(fresh)
          .then(() => {})
          .catch(() => {})
      );
    } else {
      setBinanceStatus(null);
    }

    await Promise.all(jobs);
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const tg = (window as any).Telegram?.WebApp;
      if (tg) {
        tg.ready?.();
        tg.expand?.();
        if (!getCurrentUser() && tg.initData) {
          loginTelegramWebApp(tg.initData)
            .then((res) => {
              setUser(res.user);
              refreshTelemetry(true);
            })
            .catch(() => {});
        }
      }
    }

    refreshTelemetry(false);
    warmAuthenticatedSession();

    const interval = setInterval(() => {
      if (typeof document !== "undefined" && document.visibilityState === "visible") {
        refreshTelemetry(false);
      }
    }, 45_000);

    return () => clearInterval(interval);
  }, [refreshTelemetry]);

  const { isConnected: wsConnected } = useWebSocket((msg) => {
    if (msg.type === "bcv_update" && msg.data) {
      setBcv((prev) => ({ ...(prev || {}), ...msg.data }));
    } else if (msg.type === "bot_status" && msg.data) {
      setBotStatus((prev) => ({ ...(prev || {}), ...msg.data }));
    }
  });

  return (
    <TelemetryContext.Provider
      value={{
        user,
        bcv,
        botStatus,
        binanceStatus,
        wsConnected,
        setBotStatus,
        refreshTelemetry,
      }}
    >
      {children}
    </TelemetryContext.Provider>
  );
}

export function useTelemetry(): TelemetryContextValue {
  return useContext(TelemetryContext);
}
