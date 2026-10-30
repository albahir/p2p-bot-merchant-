/**
 * Cliente de API tipado para comunicarse con FastAPI.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export interface User {
  id: number;
  username: string;
  role: "ADMIN" | "TRADER" | "INVITADO";
  telegram_id?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in_seconds: number;
  user: User;
}

export interface BCVRates {
  usd: number;
  eur?: number | null;
  cny?: number | null;
  fecha_valor?: string | null;
  p2p_usdt_ref: number;
  brecha_pct: number;
  timestamp: string;
}

export interface RateQuote {
  bank_name: string;
  buy_rate: number;
  sell_rate: number;
  spread_ves: number;
  spread_pct: number;
  total_ads: number;
  liquidity_pct: number;
  updated_at: string;
}

export interface BestArbitrage {
  buy_bank: string;
  buy_rate: number;
  sell_bank: string;
  sell_rate: number;
  spread_ves: number;
  spread_pct: number;
  net_profit_ves: number;
  is_viable: boolean;
  warning_message: string;
}

export interface ArbitrageMatrix {
  quotes: RateQuote[];
  best_arbitrage?: BestArbitrage | null;
  bcv_official_usd: number;
  bcv_brecha_pct: number;
  timestamp: string;
}

export interface OrderItem {
  id: number;
  order_number: string;
  trade_type: "BUY" | "SELL";
  asset: string;
  fiat: string;
  fiat_amount: number;
  crypto_amount: number;
  unit_price: number;
  fee_fiat: number;
  fee_crypto: number;
  bcv_rate: number;
  order_status: string;
  counterparty_name?: string | null;
  created_at: string;
}

export interface OrderListResponse {
  total: number;
  page: number;
  page_size: number;
  items: OrderItem[];
}

export interface BotStatus {
  is_running: boolean;
  is_paused: boolean;
  use_sandbox: boolean;
  active_alerts_count: number;
  environment: string;
  timestamp: string;
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("p2p_token");
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = "Error en la petición";
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errorDetail;
    } catch {
      // Ignorar fallo de parseo JSON
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

// Métodos de autenticación
export async function login(username: string, password: string): Promise<AuthResponse> {
  const res = await apiRequest<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  if (typeof window !== "undefined") {
    localStorage.setItem("p2p_token", res.access_token);
    localStorage.setItem("p2p_user", JSON.stringify(res.user));
  }
  return res;
}

export async function loginTelegram(data: Record<string, any>): Promise<AuthResponse> {
  const res = await apiRequest<AuthResponse>("/api/auth/telegram", {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (typeof window !== "undefined") {
    localStorage.setItem("p2p_token", res.access_token);
    localStorage.setItem("p2p_user", JSON.stringify(res.user));
  }
  return res;
}

export async function loginTelegramWebApp(initData: string): Promise<AuthResponse> {
  const res = await apiRequest<AuthResponse>("/api/auth/telegram-webapp", {
    method: "POST",
    body: JSON.stringify({ init_data: initData }),
  });
  if (typeof window !== "undefined") {
    localStorage.setItem("p2p_token", res.access_token);
    localStorage.setItem("p2p_user", JSON.stringify(res.user));
  }
  return res;
}

export function getCurrentUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("p2p_user");
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function logout(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("p2p_token");
    localStorage.removeItem("p2p_user");
    window.location.href = "/login";
  }
}

// Métodos de mercado y spreads
export async function getBCVRates(): Promise<BCVRates> {
  return apiRequest<BCVRates>("/api/spreads/bcv");
}

export async function getArbitrageMatrix(amountUsdt = 100): Promise<ArbitrageMatrix> {
  return apiRequest<ArbitrageMatrix>(`/api/spreads/matrix?amount_usdt=${amountUsdt}`);
}

// Métodos de órdenes
export async function getOrders(params: {
  page?: number;
  page_size?: number;
  trade_type?: string;
  search?: string;
}): Promise<OrderListResponse> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", params.page.toString());
  if (params.page_size) query.set("page_size", params.page_size.toString());
  if (params.trade_type) query.set("trade_type", params.trade_type);
  if (params.search) query.set("search", params.search);
  return apiRequest<OrderListResponse>(`/api/orders?${query.toString()}`);
}

export async function syncOrders(days = 30, trade_type?: string): Promise<any> {
  return apiRequest("/api/orders/sync", {
    method: "POST",
    body: JSON.stringify({ days, trade_type }),
  });
}

export function getExportOrdersUrl(format: "xlsx" | "csv_semicolon" | "csv_comma"): string {
  const token = getToken();
  return `${API_BASE_URL}/api/orders/export?format=${format}&token=${token || ""}`;
}

// Métodos de control de Bot
export async function getBotStatus(): Promise<BotStatus> {
  return apiRequest<BotStatus>("/api/bot/status");
}

export async function pauseBot(): Promise<any> {
  return apiRequest("/api/bot/pause", { method: "POST" });
}

export async function resumeBot(): Promise<any> {
  return apiRequest("/api/bot/resume", { method: "POST" });
}

// Métodos de administración RBAC
export async function listUsers(): Promise<User[]> {
  return apiRequest<User[]>("/api/users");
}

export async function updateUserRole(userId: number, role: "ADMIN" | "TRADER" | "INVITADO"): Promise<User> {
  return apiRequest<User>(`/api/users/${userId}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}
