"use client";

import { useEffect, useRef, useState, useCallback } from "react";

function getWsUrl(): string {
  const configured = process.env.NEXT_PUBLIC_WS_URL?.trim();
  if (configured) {
    return configured;
  }
  if (typeof window !== "undefined" && window.location?.hostname) {
    const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const port = window.location.port;
    if (!port || port === "80" || port === "443") {
      return `${wsProto}//${window.location.host}/ws/live`;
    }
    return `${wsProto}//${window.location.hostname}:8000/ws/live`;
  }
  return "ws://127.0.0.1:8000/ws/live";
}

export interface WebSocketMessage {
  type: string;
  data?: any;
  message?: string;
}

export function useWebSocket(onMessageReceived?: (msg: WebSocketMessage) => void) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const unmountedRef = useRef(false);
  const onMessageRef = useRef(onMessageReceived);

  useEffect(() => {
    onMessageRef.current = onMessageReceived;
  }, [onMessageReceived]);

  const connect = useCallback(() => {
    if (unmountedRef.current) return;
    try {
      const socket = new WebSocket(getWsUrl());
      wsRef.current = socket;

      socket.onopen = () => {
        if (!unmountedRef.current) {
          setIsConnected(true);
        }
      };

      socket.onmessage = (event) => {
        try {
          const parsed: WebSocketMessage = JSON.parse(event.data);
          if (onMessageRef.current) {
            onMessageRef.current(parsed);
          }
        } catch {
          // Ignorar frames no json
        }
      };

      socket.onclose = () => {
        if (unmountedRef.current) return;
        setIsConnected(false);
        // Reconexión automática con retroceso suave
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 3000);
      };

      socket.onerror = () => {
        socket.close();
      };
    } catch {
      if (!unmountedRef.current) {
        setIsConnected(false);
      }
    }
  }, []);

  useEffect(() => {
    unmountedRef.current = false;
    // Pequeño retardo (50ms) para evitar que el doble montaje de React StrictMode en desarrollo
    // cierre el WebSocket antes de terminar el handshake ("WebSocket is closed before connection is established").
    const initialConnectTimer = setTimeout(() => {
      connect();
    }, 50);

    // Heartbeat ping cada 25 segundos
    const interval = setInterval(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ action: "ping" }));
      }
    }, 25000);

    return () => {
      unmountedRef.current = true;
      clearTimeout(initialConnectTimer);
      clearInterval(interval);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      const sock = wsRef.current;
      if (sock) {
        if (sock.readyState === WebSocket.CONNECTING) {
          sock.onopen = () => sock.close();
        } else if (sock.readyState === WebSocket.OPEN) {
          sock.close();
        }
      }
    };
  }, [connect]);

  const sendMessage = useCallback((msg: Record<string, any>) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { isConnected, sendMessage };
}
