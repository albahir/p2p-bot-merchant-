"use client";

import { useEffect, useRef, useState, useCallback } from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://127.0.0.1:8000/ws/live";

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
      const socket = new WebSocket(WS_URL);
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
    connect();

    // Heartbeat ping cada 25 segundos
    const interval = setInterval(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ action: "ping" }));
      }
    }, 25000);

    return () => {
      unmountedRef.current = true;
      clearInterval(interval);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const sendMessage = useCallback((msg: Record<string, any>) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { isConnected, sendMessage };
}
