/**
 * Cliente de API tipado para comunicarse con FastAPI.
 */

function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (configured) {
    return configured.replace(/\/+$/, "");
  }
  if (typeof window !== "undefined" && window.location?.hostname) {
    const port = window.location.port;
    // Detrás de Caddy / Cloudflare (puertos estándar 80/443), usar mismo origen para /api/*
    if (!port || port === "80" || port === "443") {
      return "";
    }
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://127.0.0.1:8000";
}

export interface User {
  id: number;
  username: string;
  full_name?: string | null;
  tax_id?: string | null;
  email?: string | null;
  role: "ADMIN" | "TRADER" | "INVITADO";
  telegram_id?: string | null;
  google_sheet_id?: string | null;
  email_verified?: boolean;
  google_auth_type?: "OAUTH2" | "SERVICE_ACCOUNT" | string | null;
  google_oauth_connected?: boolean;
  google_account_email?: string | null;
  permission_source?: string;
  telegram_linked?: boolean;
  has_security_question?: boolean;
  has_recovery_key?: boolean;
  binance_api_configured?: boolean;
  binance_key_type?: "HMAC" | "Ed25519" | string | null;
  google_sheet_configured?: boolean;
  preferred_banks?: string[];
  bank_initial_balances?: Record<string, number>;
  is_active: boolean;
  created_at: string;
}

export const VENEZUELAN_BANK_CATALOG = [
  "Banco de Venezuela",
  "Mercantil",
  "Banesco",
  "Pago Móvil",
  "BBVA Provincial",
  "BNC",
  "Bancamiga",
  "Bancaribe",
  "Banplus",
  "Banco del Tesoro",
] as const;

export function canonicalBankName(rawName: string): string {
  const cleaned = (rawName || "").trim();
  if (!cleaned) return "";
  const low = cleaned.toLowerCase();
  if (
    low === "venezuela" ||
    low === "bdv" ||
    low.includes("banco de venezuela") ||
    low === "specificbank"
  ) {
    return "Banco de Venezuela";
  }
  if (low.includes("banesco")) return "Banesco";
  if (low.includes("mercantil")) return "Mercantil";
  if (low.includes("pago móvil") || low.includes("pago movil") || low === "pagomovil") {
    return "Pago Móvil";
  }
  if (low.includes("provincial") || low.includes("bbva")) return "BBVA Provincial";
  if (low === "bnc" || low.includes("banco nacional de crédito") || low.includes("bnc ")) {
    return "BNC";
  }
  if (low.includes("bancamiga")) return "Bancamiga";
  if (low.includes("bancaribe")) return "Bancaribe";
  if (low.includes("banplus")) return "Banplus";
  if (low.includes("tesoro")) return "Banco del Tesoro";
  if (low.includes("fondo común") || low === "bfc") return "BFC";
  return cleaned;
}

export function bankMatchesProfile(candidateBank: string, userBanks: string[]): boolean {
  if (!candidateBank || !userBanks || userBanks.length === 0) return false;
  const candCanon = canonicalBankName(candidateBank).toLowerCase();
  for (const ub of userBanks) {
    const userCanon = canonicalBankName(ub).toLowerCase();
    if (!userCanon) continue;
    if (candCanon === userCanon || candCanon.includes(userCanon) || userCanon.includes(candCanon)) {
      return true;
    }
  }
  return false;
}

export function resolveUserBankBalance(
  candidateBank: string,
  balances?: Record<string, number> | null
): number {
  if (!candidateBank || !balances) return 0;
  const candCanon = canonicalBankName(candidateBank);
  if (typeof balances[candCanon] === "number") {
    return balances[candCanon];
  }
  for (const [k, val] of Object.entries(balances)) {
    if (bankMatchesProfile(candidateBank, [k])) {
      return Number(val) || 0;
    }
  }
  return 0;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in_seconds: number;
  user: User;
  recovery_key?: string | null;
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

export interface OrderbookAd {
  adv_no: string;
  trade_type: "BUY" | "SELL" | string;
  price: number;
  surplus_usdt: number;
  min_ves: number;
  max_ves: number;
  min_usdt: number;
  max_usdt: number;
  nick_name: string;
  month_orders: number;
  finish_rate_pct: number;
  is_merchant: boolean;
  banks: string[];
}

export interface FilteredOrderbook {
  amount_usdt: number;
  trans_amount_ves: number;
  bank_filter: string;
  pay_types: string[];
  merchant_only: boolean;
  best_buy_price: number;
  best_sell_price: number;
  price_spread_ves: number;
  price_spread_pct: number;
  taker_spread_ves: number;
  taker_spread_pct: number;
  maker_spread_ves: number;
  maker_spread_pct: number;
  recommended_mode: "MAKER" | "TAKER" | "NONE" | string;
  net_profit_ves: number;
  net_profit_usdt: number;
  buy_ads: OrderbookAd[];
  sell_ads: OrderbookAd[];
  source: string;
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

function formatApiErrorDetail(rawDetail: unknown, fallback: string): string {
  if (!rawDetail) return fallback;
  if (typeof rawDetail === "string") return rawDetail;
  if (Array.isArray(rawDetail)) {
    return rawDetail
      .map((item: any) => item?.msg || JSON.stringify(item))
      .join("; ");
  }
  return String(rawDetail);
}

export interface ApiRequestOptions extends RequestInit {
  /** Ignorar caché en memoria y forzar petición real a red. */
  fresh?: boolean;
  /** Tiempo de vida en caché en memoria para GET (ms). 0 desactiva caché. */
  cacheTtlMs?: number;
  /** Prioridad Fetch API nativa ('high' | 'low' | 'auto'). */
  priority?: "high" | "low" | "auto";
}

const DEFAULT_GET_CACHE_TTL_MS = 15_000;
const _inFlightGets = new Map<string, Promise<unknown>>();
const _responseCache = new Map<string, { data: unknown; expiresAt: number }>();

export function clearApiCache(endpointPrefix?: string): void {
  if (!endpointPrefix) {
    _responseCache.clear();
    return;
  }
  for (const key of _responseCache.keys()) {
    if (key.includes(endpointPrefix)) {
      _responseCache.delete(key);
    }
  }
}

function resolveCacheKey(endpoint: string): string {
  const isPublicEndpoint =
    endpoint.startsWith("/api/spreads/") ||
    endpoint.startsWith("/api/market/") ||
    endpoint.startsWith("/api/auth/login") ||
    endpoint.startsWith("/api/auth/register") ||
    endpoint.startsWith("/api/auth/email/") ||
    endpoint.startsWith("/api/auth/telegram-bot-info") ||
    endpoint.startsWith("/api/auth/recover-") ||
    endpoint.startsWith("/api/auth/reset-password");
  const token = getToken();
  const tokenScope = isPublicEndpoint ? "public" : token ? token.slice(-12) : "anon";
  return `GET:${tokenScope}:${endpoint}`;
}

/** Lectura síncrona de caché en memoria para hidratar vistas en 0 ms al cambiar de pestaña. */
export function getCachedApiResponse<T>(endpoint: string): T | null {
  const key = resolveCacheKey(endpoint);
  const cached = _responseCache.get(key);
  if (cached && Date.now() < cached.expiresAt) {
    return cached.data as T;
  }
  return null;
}

/** Planifica tareas no bloqueantes con Prioritized Task Scheduling API (`scheduler.postTask`) y fallback a `setTimeout`. */
function scheduleBackgroundTask(task: () => void): void {
  if (typeof window === "undefined") return;
  const win = window as unknown as {
    scheduler?: {
      postTask?: (cb: () => void, opts?: { priority?: string }) => Promise<unknown>;
    };
  };
  if (win.scheduler && typeof win.scheduler.postTask === "function") {
    void win.scheduler.postTask(task, { priority: "background" }).catch(() => {});
  } else {
    setTimeout(task, 0);
  }
}

export async function apiRequest<T>(
  endpoint: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const { fresh = false, cacheTtlMs, priority, ...fetchInit } = options;
  const method = (fetchInit.method || "GET").toUpperCase();
  const token = getToken();
  const headers = new Headers(fetchInit.headers || {});

  if (
    method !== "GET" &&
    method !== "HEAD" &&
    !headers.has("Content-Type") &&
    !(fetchInit.body instanceof FormData)
  ) {
    headers.set("Content-Type", "application/json");
  }
  const isPublicEndpoint =
    endpoint.startsWith("/api/spreads/") ||
    endpoint.startsWith("/api/market/") ||
    endpoint.startsWith("/api/auth/login") ||
    endpoint.startsWith("/api/auth/register") ||
    endpoint.startsWith("/api/auth/email/") ||
    endpoint.startsWith("/api/auth/telegram-bot-info") ||
    endpoint.startsWith("/api/auth/recover-") ||
    endpoint.startsWith("/api/auth/reset-password");

  if (token && !isPublicEndpoint && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  // Las mutaciones invalidan la caché en memoria para reflejar los datos nuevos al instante
  if (method !== "GET") {
    _responseCache.clear();
  }

  const effectiveTtl =
    method === "GET" ? (cacheTtlMs !== undefined ? cacheTtlMs : DEFAULT_GET_CACHE_TTL_MS) : 0;
  const tokenScope = isPublicEndpoint ? "public" : token ? token.slice(-12) : "anon";
  const cacheKey = `${method}:${tokenScope}:${endpoint}`;

  if (method === "GET" && !fresh && effectiveTtl > 0) {
    const cached = _responseCache.get(cacheKey);
    if (cached && Date.now() < cached.expiresAt) {
      return cached.data as T;
    }
  }

  if (method === "GET" && !fresh) {
    const inFlight = _inFlightGets.get(cacheKey);
    if (inFlight) {
      return inFlight as Promise<T>;
    }
  }

  const requestInit: RequestInit & { priority?: "high" | "low" | "auto" } = {
    ...fetchInit,
    method,
    headers,
  };
  if (priority) {
    requestInit.priority = priority;
  }

  const executeFetch = async (): Promise<T> => {
    const response = await fetch(`${getApiBaseUrl()}${endpoint}`, requestInit);

    if (!response.ok) {
      if (
        response.status === 401 &&
        typeof window !== "undefined" &&
        !endpoint.startsWith("/api/auth/")
      ) {
        localStorage.removeItem("p2p_token");
        localStorage.removeItem("p2p_user");
        _responseCache.clear();
      }
      let errorDetail = "Error en la petición";
      try {
        const errJson = await response.json();
        errorDetail = formatApiErrorDetail(errJson.detail, errorDetail);
      } catch {
        // Ignorar fallo de parseo JSON
      }
      throw new Error(errorDetail);
    }

    const payload = (await response.json()) as T;
    if (method === "GET" && effectiveTtl > 0) {
      _responseCache.set(cacheKey, {
        data: payload,
        expiresAt: Date.now() + effectiveTtl,
      });
    }
    return payload;
  };

  if (method === "GET" && !fresh) {
    const promise = executeFetch().finally(() => {
      _inFlightGets.delete(cacheKey);
    });
    _inFlightGets.set(cacheKey, promise);
    return promise;
  }

  return executeFetch();
}

export async function downloadAuthenticatedFile(
  endpoint: string,
  fallbackFilename: string
): Promise<void> {
  const token = getToken();
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${getApiBaseUrl()}${endpoint}`, {
    method: "GET",
    headers,
  });

  if (!response.ok) {
    let errorDetail = "No se pudo descargar el archivo solicitado.";
    try {
      const errJson = await response.json();
      errorDetail = formatApiErrorDetail(errJson.detail, errorDetail);
    } catch {
      // Ignorar fallo de parseo JSON
    }
    throw new Error(errorDetail);
  }

  const blob = await response.blob();
  let filename = fallbackFilename;
  const disposition = response.headers.get("content-disposition");
  if (disposition) {
    const match = disposition.match(/filename="?([^";]+)"?/i);
    if (match?.[1]) {
      filename = match[1];
    }
  }

  const blobUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(blobUrl);
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
    warmAuthenticatedSession();
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
    warmAuthenticatedSession();
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
    warmAuthenticatedSession();
  }
  return res;
}

export function getCurrentUser(): User | null {
  if (typeof window === "undefined") return null;
  const token = localStorage.getItem("p2p_token");
  const raw = localStorage.getItem("p2p_user");
  if (!token || !raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function logout(): void {
  if (typeof window !== "undefined") {
    clearApiCache();
    localStorage.removeItem("p2p_token");
    localStorage.removeItem("p2p_user");
    localStorage.removeItem("p2p_sheets_config");
    window.location.href = "/login";
  }
}

/**
 * Precarga segura y despriorizada (`priority: 'low'` + `scheduler.postTask` background)
 * de todas las conexiones e indicadores existentes tras iniciar sesión, sin exponer secretos.
 */
export function warmAuthenticatedSession(): void {
  if (typeof window === "undefined") return;
  const user = getCurrentUser();
  const hasTrader = Boolean(user && (user.role === "ADMIN" || user.role === "TRADER"));

  scheduleBackgroundTask(() => {
    void getBCVRates(false).catch(() => {});
    void apiRequest("/api/spreads/matrix?amount_usdt=100&merchant_only=false", {
      priority: "low",
      cacheTtlMs: 30_000,
    }).catch(() => {});

    if (!hasTrader) return;

    void getSheetsSettings(false).catch(() => {});
    void apiRequest("/api/settings/binance", { priority: "low", cacheTtlMs: 45_000 }).catch(() => {});
    void apiRequest("/api/settings/telegram", { priority: "low", cacheTtlMs: 45_000 }).catch(() => {});
    void apiRequest("/api/orders?page=1&page_size=20", { priority: "low", cacheTtlMs: 30_000 }).catch(() => {});
    void apiRequest("/api/fiscal/summary?cost_method=FIFO", { priority: "low", cacheTtlMs: 30_000 }).catch(() => {});

    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth() + 1;
    void apiRequest(
      `/api/accounting/balances/live?year=${year}&month=${month}&initial_usdt=0&initial_ves=0`,
      { priority: "low", cacheTtlMs: 30_000 }
    ).catch(() => {});
    void apiRequest("/api/accounting/journal?", { priority: "low", cacheTtlMs: 30_000 }).catch(() => {});
  });
}

/** Pre-calienta los GET iniciales de una ruta con prioridad baja al hacer hover en la barra. */
export function prefetchRouteData(href: string): void {
  if (typeof window === "undefined") return;
  const user = getCurrentUser();
  const hasTrader = Boolean(user && (user.role === "ADMIN" || user.role === "TRADER"));

  if (href === "/" || href === "/calculator") {
    void apiRequest("/api/spreads/matrix?amount_usdt=100&merchant_only=false", { priority: "low" }).catch(() => {});
    return;
  }
  if (href === "/market") {
    void apiRequest("/api/market/candles?side=sell&timeframe=5m&bank=*&ticket_ves=1000000&limit=240", {
      priority: "low",
    }).catch(() => {});
    void apiRequest("/api/market/analytics?bank=*&ticket_ves=1000000", {
      priority: "low",
    }).catch(() => {});
    return;
  }
  if (!hasTrader) return;
  if (href === "/orders") {
    void apiRequest("/api/orders?page=1&page_size=20", { priority: "low" }).catch(() => {});
    void apiRequest("/api/fiscal/summary?cost_method=FIFO", { priority: "low" }).catch(() => {});
  } else if (href === "/sheets") {
    void getSheetsSettings(false).catch(() => {});
  } else if (href === "/settings") {
    void apiRequest("/api/settings/binance", { priority: "low" }).catch(() => {});
    void apiRequest("/api/settings/telegram", { priority: "low" }).catch(() => {});
  } else if (href === "/accounting") {
    const now = new Date();
    void apiRequest(
      `/api/accounting/balances/live?year=${now.getFullYear()}&month=${now.getMonth() + 1}&initial_usdt=0&initial_ves=0`,
      { priority: "low" }
    ).catch(() => {});
    void apiRequest("/api/accounting/journal?", { priority: "low" }).catch(() => {});
  }
}

// Caché en memoria y deduplicación de peticiones en vuelo para tasas BCV
// (Evita consultas duplicadas entre AppShell y las páginas dado que el BCV cambia 1 vez por día hábil)
let _bcvCacheData: BCVRates | null = null;
let _bcvCacheTimestamp = 0;
let _bcvInFlight: Promise<BCVRates> | null = null;
const BCV_CLIENT_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutos

// Métodos de mercado y spreads
export async function getBCVRates(forceRefresh = false): Promise<BCVRates> {
  const now = Date.now();
  if (!forceRefresh && _bcvCacheData && now - _bcvCacheTimestamp < BCV_CLIENT_CACHE_TTL_MS) {
    return _bcvCacheData;
  }
  if (!forceRefresh && _bcvInFlight) {
    return _bcvInFlight;
  }
  _bcvInFlight = apiRequest<BCVRates>("/api/spreads/bcv")
    .then((data) => {
      _bcvCacheData = data;
      _bcvCacheTimestamp = Date.now();
      return data;
    })
    .finally(() => {
      _bcvInFlight = null;
    });
  return _bcvInFlight;
}

export async function getArbitrageMatrix(
  amountUsdt = 100,
  merchantOnly = false
): Promise<ArbitrageMatrix> {
  const query = new URLSearchParams({
    amount_usdt: String(amountUsdt),
    merchant_only: String(merchantOnly),
  });
  return apiRequest<ArbitrageMatrix>(`/api/spreads/matrix?${query.toString()}`);
}

export async function getFilteredOrderbook(params: {
  amount_usdt?: number;
  amount_ves?: number | null;
  bank?: string;
  merchant_only?: boolean;
  rows?: number;
}): Promise<FilteredOrderbook> {
  const query = new URLSearchParams();
  if (params.amount_usdt !== undefined) {
    query.set("amount_usdt", String(params.amount_usdt));
  }
  if (params.amount_ves !== undefined && params.amount_ves !== null && params.amount_ves > 0) {
    query.set("amount_ves", String(params.amount_ves));
  }
  if (params.bank) {
    query.set("bank", params.bank);
  }
  if (params.merchant_only !== undefined) {
    query.set("merchant_only", String(params.merchant_only));
  }
  if (params.rows !== undefined) {
    query.set("rows", String(params.rows));
  }
  return apiRequest<FilteredOrderbook>(`/api/spreads/orderbook?${query.toString()}`);
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

export async function uploadOrdersFile(file: File): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${getApiBaseUrl()}/api/orders/upload`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    let detail = "Error al subir archivo de órdenes";
    try {
      const errJson = await res.json();
      detail = formatApiErrorDetail(errJson.detail, detail);
    } catch {
      // Ignorar fallo de parseo JSON
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function downloadOrdersExport(
  format: "xlsx" | "csv_semicolon" | "csv_comma"
): Promise<void> {
  const ext = format === "xlsx" ? "xlsx" : "csv";
  return downloadAuthenticatedFile(
    `/api/orders/export?format=${format}`,
    `ordenes_p2p.${ext}`
  );
}

// Métodos de autenticación adicional (Registro y Recuperación)
export interface RegisterData {
  username: string;
  password: string;
  full_name?: string;
  tax_id?: string;
  email?: string;
  email_verification_token?: string;
  telegram_id?: string;
  google_sheet_id?: string;
  preferred_banks?: string[];
  security_question?: string;
  security_answer?: string;
}

export interface RecoveryOptions {
  has_email?: boolean;
  has_telegram: boolean;
  has_security_question: boolean;
  security_question?: string | null;
  has_recovery_key: boolean;
  is_locked: boolean;
}

export type RecoveryMethod =
  | "email_otp"
  | "telegram_otp"
  | "security_question"
  | "recovery_key";

export interface RecoveryProfileUpdateData {
  full_name?: string;
  tax_id?: string;
  email?: string;
  security_question?: string;
  security_answer?: string;
  regenerate_recovery_key?: boolean;
}

export interface TelegramBotInfo {
  available: boolean;
  bot_username: string | null;
  bot_mention: string | null;
  bot_name: string;
  bot_url: string | null;
  command: string;
}

export async function getTelegramBotInfo(): Promise<TelegramBotInfo> {
  return apiRequest<TelegramBotInfo>("/api/auth/telegram-bot-info", {
    cacheTtlMs: 300_000,
  });
}

export async function sendEmailVerificationCode(email: string): Promise<{
  sent: boolean;
  smtp_configured: boolean;
  cooldown_seconds?: number;
  message: string;
}> {
  return apiRequest("/api/auth/email/send-code", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function verifyEmailCode(
  email: string,
  code: string
): Promise<{
  verified: boolean;
  email: string;
  verification_token: string;
  message: string;
}> {
  return apiRequest("/api/auth/email/verify-code", {
    method: "POST",
    body: JSON.stringify({ email, code }),
  });
}

export async function registerUser(data: RegisterData): Promise<AuthResponse> {
  const res = await apiRequest<AuthResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (typeof window !== "undefined") {
    localStorage.setItem("p2p_token", res.access_token);
    localStorage.setItem("p2p_user", JSON.stringify(res.user));
  }
  return res;
}

export async function getRecoveryOptions(usernameOrEmail: string): Promise<RecoveryOptions> {
  return apiRequest<RecoveryOptions>("/api/auth/recover-options", {
    method: "POST",
    body: JSON.stringify({ username: usernameOrEmail }),
  });
}

export async function recoverPassword(
  username: string,
  channel: "telegram" | "email" = "telegram"
): Promise<{
  success: boolean;
  message: string;
  has_telegram?: boolean;
  has_email?: boolean;
  debug_code?: string;
}> {
  return apiRequest("/api/auth/recover-password", {
    method: "POST",
    body: JSON.stringify({ username, channel }),
  });
}

export async function resetPassword(
  username: string,
  reset_code: string,
  new_password: string,
  method: RecoveryMethod = "telegram_otp"
): Promise<{ success: boolean; message: string; new_recovery_key?: string | null }> {
  return apiRequest("/api/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ username, reset_code, new_password, method }),
  });
}

export async function getMyProfile(): Promise<User> {
  return apiRequest<User>("/api/auth/me");
}

export async function updateRecoveryProfile(data: RecoveryProfileUpdateData): Promise<{
  success: boolean;
  message: string;
  user: User;
  recovery_key?: string | null;
}> {
  const res = await apiRequest<{
    success: boolean;
    message: string;
    user: User;
    recovery_key?: string | null;
  }>("/api/auth/recovery-profile", {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (typeof window !== "undefined" && res.user) {
    localStorage.setItem("p2p_user", JSON.stringify(res.user));
  }
  return res;
}

// Métodos de configuración y diagnóstico de Binance API
export interface BinanceStatusResponse {
  is_configured: boolean;
  api_key_masked: string;
  key_type: "HMAC" | "Ed25519" | string;
  is_connected: boolean;
  latency_ms: number;
  clock_drift_ms: number;
  used_weight: number;
  max_weight: number;
  permissions: string[];
  message: string;
}

export interface SaveBinanceKeysRequest {
  api_key: string;
  secret_key: string;
  key_type: "HMAC" | "Ed25519";
}

export interface VerifyBinanceResponse {
  success: boolean;
  is_connected: boolean;
  latency_ms: number;
  clock_drift_ms: number;
  used_weight: number;
  max_weight: number;
  is_weight_safe: boolean;
  server_time_utc?: string | null;
  message: string;
}

export async function getBinanceSettings(): Promise<BinanceStatusResponse> {
  return apiRequest<BinanceStatusResponse>("/api/settings/binance");
}

export async function saveBinanceSettings(data: SaveBinanceKeysRequest): Promise<BinanceStatusResponse> {
  return apiRequest<BinanceStatusResponse>("/api/settings/binance", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function verifyBinanceConnection(): Promise<VerifyBinanceResponse> {
  return apiRequest<VerifyBinanceResponse>("/api/settings/binance/verify", {
    method: "POST",
  });
}

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

export async function updateUserStatus(userId: number, isActive: boolean): Promise<User> {
  return apiRequest<User>(`/api/users/${userId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
}

export async function authorizeTelegramUser(data: {
  telegram_id: string;
  username?: string;
  role?: "ADMIN" | "TRADER" | "INVITADO";
}): Promise<User> {
  return apiRequest<User>("/api/users/authorize-telegram", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateUserSheet(userId: number, googleSheetId: string | null): Promise<User> {
  return apiRequest<User>(`/api/users/${userId}/sheet`, {
    method: "PATCH",
    body: JSON.stringify({ google_sheet_id: googleSheetId }),
  });
}

// Métodos de Google Sheets y Telegram
export interface GoogleSheetsConfigResponse {
  google_sheet_id?: string | null;
  google_sheet_url?: string | null;
  google_auth_type: "SERVICE_ACCOUNT" | "OAUTH2" | string;
  service_account_email?: string | null;
  oauth_available?: boolean;
  oauth_connected?: boolean;
  google_account_email?: string | null;
  oauth_custom_configured?: boolean;
  is_connected: boolean;
  message: string;
}

export interface GoogleSheetsSyncResponse {
  success: boolean;
  google_sheet_id?: string | null;
  google_sheet_url?: string | null;
  rows_exported: number;
  journal_entries_exported: number;
  service_account_email?: string | null;
  oauth_connected?: boolean;
  message: string;
}

export interface TelegramStatusResponse {
  is_configured: boolean;
  bot_token_masked: string;
  linked_chat_id?: string | null;
  fail_closed_5xx_enabled: boolean;
  weight_pause_enabled: boolean;
  log_sanitization_enabled: boolean;
  message: string;
}

const SHEETS_CONFIG_STORAGE_KEY = "p2p_sheets_config";

function persistSheetsConfigCache(cfg: GoogleSheetsConfigResponse): GoogleSheetsConfigResponse {
  if (typeof window !== "undefined") {
    try {
      localStorage.setItem(SHEETS_CONFIG_STORAGE_KEY, JSON.stringify(cfg));
      const current = getCurrentUser();
      if (current) {
        const updatedUser: User = {
          ...current,
          google_sheet_id: cfg.google_sheet_id ?? null,
          google_auth_type: cfg.google_auth_type,
          google_oauth_connected: Boolean(cfg.oauth_connected),
          google_account_email: cfg.google_account_email ?? null,
          google_sheet_configured: Boolean(cfg.google_sheet_id || cfg.oauth_connected),
        };
        localStorage.setItem("p2p_user", JSON.stringify(updatedUser));
      }
    } catch {
      // Ignorar fallo de cuota en localStorage
    }
  }
  return cfg;
}

export function getCachedSheetsSettings(): GoogleSheetsConfigResponse | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(SHEETS_CONFIG_STORAGE_KEY);
    if (raw) {
      return JSON.parse(raw) as GoogleSheetsConfigResponse;
    }
  } catch {
    // Fallback a datos derivados del usuario en sesión
  }

  const user = getCurrentUser();
  if (!user) return null;
  const hasSheet = Boolean(user.google_sheet_id);
  const oauthConnected = Boolean(user.google_oauth_connected);
  if (!hasSheet && !oauthConnected) return null;

  return {
    google_sheet_id: user.google_sheet_id ?? null,
    google_sheet_url: user.google_sheet_id
      ? `https://docs.google.com/spreadsheets/d/${user.google_sheet_id}`
      : null,
    google_auth_type: user.google_auth_type || (oauthConnected ? "OAUTH2" : "SERVICE_ACCOUNT"),
    oauth_connected: oauthConnected,
    google_account_email: user.google_account_email ?? null,
    is_connected: hasSheet || oauthConnected,
    message: "Google Sheets listo para sincronizar.",
  };
}

export async function getSheetsSettings(fresh = false): Promise<GoogleSheetsConfigResponse> {
  const res = await apiRequest<GoogleSheetsConfigResponse>("/api/settings/sheets", {
    fresh,
    cacheTtlMs: 45_000,
  });
  return persistSheetsConfigCache(res);
}

export async function saveSheetsSettings(data: {
  google_sheet_id: string | null;
  google_auth_type?: "SERVICE_ACCOUNT" | "OAUTH2";
}): Promise<GoogleSheetsConfigResponse> {
  const res = await apiRequest<GoogleSheetsConfigResponse>("/api/settings/sheets", {
    method: "POST",
    body: JSON.stringify({
      google_sheet_id: data.google_sheet_id,
      google_auth_type: data.google_auth_type || "SERVICE_ACCOUNT",
    }),
  });
  return persistSheetsConfigCache(res);
}

export async function startGoogleOAuth(redirectUri?: string): Promise<{ authorization_url: string }> {
  const qs = redirectUri ? `?redirect_uri=${encodeURIComponent(redirectUri)}` : "";
  return apiRequest<{ authorization_url: string }>(`/api/settings/sheets/oauth/start${qs}`);
}

export async function completeGoogleOAuth(data: {
  code: string;
  state: string;
  redirect_uri?: string;
}): Promise<GoogleSheetsConfigResponse> {
  const res = await apiRequest<GoogleSheetsConfigResponse>("/api/settings/sheets/oauth/callback", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return persistSheetsConfigCache(res);
}

export async function saveGoogleOAuthClientConfig(data: {
  client_id: string;
  client_secret: string;
  redirect_uri?: string;
}): Promise<GoogleSheetsConfigResponse> {
  const res = await apiRequest<GoogleSheetsConfigResponse>("/api/settings/sheets/oauth/credentials", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return persistSheetsConfigCache(res);
}

export async function disconnectGoogleOAuth(): Promise<GoogleSheetsConfigResponse> {
  const res = await apiRequest<GoogleSheetsConfigResponse>("/api/settings/sheets/oauth/disconnect", {
    method: "POST",
  });
  return persistSheetsConfigCache(res);
}

export async function syncSheetsNow(): Promise<GoogleSheetsSyncResponse> {
  return apiRequest<GoogleSheetsSyncResponse>("/api/settings/sheets/sync", {
    method: "POST",
  });
}

export async function getTelegramSettings(): Promise<TelegramStatusResponse> {
  return apiRequest<TelegramStatusResponse>("/api/settings/telegram");
}

export async function sendTelegramTestAlert(): Promise<{ success: boolean; message: string }> {
  return apiRequest<{ success: boolean; message: string }>("/api/settings/telegram/test", {
    method: "POST",
  });
}

// Perfil Bancario del Operador (Bancos con los que trabaja y Saldos Iniciales por Banco)
export interface UserBanksConfigResponse {
  preferred_banks: string[];
  bank_initial_balances: Record<string, number>;
  total_initial_ves: number;
  message: string;
}

const USER_BANKS_STORAGE_KEY = "p2p_user_banks_config";

function persistUserBanksCache(cfg: UserBanksConfigResponse): UserBanksConfigResponse {
  if (typeof window !== "undefined") {
    try {
      localStorage.setItem(USER_BANKS_STORAGE_KEY, JSON.stringify(cfg));
      const current = getCurrentUser();
      if (current) {
        const updatedUser: User = {
          ...current,
          preferred_banks: cfg.preferred_banks,
          bank_initial_balances: cfg.bank_initial_balances,
        };
        localStorage.setItem("p2p_user", JSON.stringify(updatedUser));
      }
    } catch {
      // Ignorar fallo de cuota en localStorage
    }
  }
  return cfg;
}

export function getCachedUserBanks(): UserBanksConfigResponse {
  if (typeof window !== "undefined") {
    const user = getCurrentUser();
    if (
      user &&
      ((user.preferred_banks && user.preferred_banks.length > 0) ||
        (user.bank_initial_balances && Object.keys(user.bank_initial_balances).length > 0))
    ) {
      const prefs = (user.preferred_banks || []).map(canonicalBankName).filter(Boolean);
      const bals: Record<string, number> = {};
      for (const [k, v] of Object.entries(user.bank_initial_balances || {})) {
        const c = canonicalBankName(k);
        if (c) bals[c] = Number(v) || 0;
      }
      for (const b of prefs) {
        if (!(b in bals)) bals[b] = 0;
      }
      const total = Object.values(bals).reduce((acc, n) => acc + (Number(n) || 0), 0);
      return {
        preferred_banks: prefs,
        bank_initial_balances: bals,
        total_initial_ves: total,
        message: "Perfil bancario hidratado de sesión.",
      };
    }

    try {
      const raw = localStorage.getItem(USER_BANKS_STORAGE_KEY);
      if (raw) {
        return JSON.parse(raw) as UserBanksConfigResponse;
      }
    } catch {
      // Ignorar errores de parseo
    }
  }
  return {
    preferred_banks: [],
    bank_initial_balances: {},
    total_initial_ves: 0,
    message: "",
  };
}

export async function getUserBanksSettings(): Promise<UserBanksConfigResponse> {
  const res = await apiRequest<UserBanksConfigResponse>("/api/settings/banks");
  return persistUserBanksCache(res);
}

export async function saveUserBanksSettings(data: {
  preferred_banks: string[];
  bank_initial_balances: Record<string, number>;
}): Promise<UserBanksConfigResponse> {
  const cleanPrefs = Array.from(
    new Set((data.preferred_banks || []).map(canonicalBankName).filter(Boolean))
  );
  const cleanBals: Record<string, number> = {};
  for (const b of cleanPrefs) {
    cleanBals[b] = Math.max(0, Number(data.bank_initial_balances?.[b] ?? 0));
  }
  // Persistir localmente de inmediato (0 ms) incluso para usuarios sin sesión o mientras responde el servidor
  const optimistic: UserBanksConfigResponse = {
    preferred_banks: cleanPrefs,
    bank_initial_balances: cleanBals,
    total_initial_ves: Object.values(cleanBals).reduce((acc, v) => acc + v, 0),
    message: "Guardado localmente.",
  };
  persistUserBanksCache(optimistic);

  const token = getToken();
  if (!token) {
    return optimistic;
  }

  try {
    const res = await apiRequest<UserBanksConfigResponse>("/api/settings/banks", {
      method: "POST",
      body: JSON.stringify({
        preferred_banks: cleanPrefs,
        bank_initial_balances: cleanBals,
      }),
    });
    return persistUserBanksCache(res);
  } catch {
    return optimistic;
  }
}

// Métodos de Reconciliación Fiscal P2P (6 Piezas)
export interface FiscalSummary {
  period: string;
  initial_balance: number;
  inflows_p2p_buys: number;
  total_inflows: number;
  outflows_p2p_sells: number;
  total_outflows: number;
  volume_operated: number;
  volume_operated_ves?: number;
  total_fees: number;
  total_fees_ves?: number;
  calculated_final_balance: number;
  actual_final_balance: number;
  discrepancy: number;
  gross_revenue_ves: number;
  acquisition_cost_ves: number;
  net_profit_ves: number;
  net_profit_usd: number;
  status: string;
  orders_count: number;
  message: string;
  bcv_rate: number;
  cost_method?: string;
}

export async function getFiscalSummary(
  period?: string,
  initial_balance?: number,
  actual_final_balance?: number,
  cost_method: "FIFO" | "AVG" = "FIFO"
): Promise<FiscalSummary> {
  const query = new URLSearchParams();
  if (period) query.set("period", period);
  if (initial_balance !== undefined) query.set("initial_balance", initial_balance.toString());
  if (actual_final_balance !== undefined) query.set("actual_final_balance", actual_final_balance.toString());
  query.set("cost_method", cost_method);
  return apiRequest<FiscalSummary>(`/api/fiscal/summary?${query.toString()}`);
}

export async function closeFiscalPeriod(data: {
  period: string;
  initial_balance: number;
  actual_final_balance?: number;
  asset?: string;
  cost_method?: "FIFO" | "AVG";
}): Promise<FiscalSummary> {
  return apiRequest<FiscalSummary>("/api/fiscal/reconcile", {
    method: "POST",
    body: JSON.stringify({
      period: data.period,
      initial_balance: data.initial_balance,
      actual_final_balance: data.actual_final_balance,
      asset: data.asset || "USDT",
      cost_method: data.cost_method || "FIFO",
    }),
  });
}

export async function getFiscalSnapshot(period: string): Promise<{
  period: string;
  is_closed: boolean;
  snapshot?: Record<string, any> | null;
}> {
  const query = new URLSearchParams({ period });
  return apiRequest(`/api/fiscal/snapshot?${query.toString()}`);
}

// Métodos de Contabilidad P2P (Libro Diario y Libro Mayor - SPEC-017)
export interface JournalEntryItem {
  id?: number | null;
  entry_number: number;
  date_time: string;
  account_code: string;
  account_name: string;
  debit: number;
  credit: number;
  reference: string;
  description: string;
  voucher_id?: number | null;
  order_number?: string | null;
  entry_hash: string;
}

export interface LedgerSummaryItem {
  account_code: string;
  account_name: string;
  year: number;
  month: number;
  initial_balance: number;
  total_debit: number;
  total_credit: number;
  final_balance: number;
  entries_count: number;
}

export interface UploadVoucherResponse {
  voucher_id: number;
  bank_name: string;
  reference_number: string;
  amount_ves: number;
  bank_fee_ves: number;
  payment_method: string;
  verification_status: string;
  matched_order_number?: string | null;
}

export async function getJournalEntries(
  startDate?: string,
  endDate?: string,
  accountCode?: string
): Promise<JournalEntryItem[]> {
  const query = new URLSearchParams();
  if (startDate) query.set("start_date", startDate);
  if (endDate) query.set("end_date", endDate);
  if (accountCode) query.set("account_code", accountCode);
  return apiRequest<JournalEntryItem[]>(`/api/accounting/journal?${query.toString()}`);
}

export async function getLedgerSummaries(
  year: number,
  month: number,
  accountCode?: string,
  initialBalance?: number
): Promise<LedgerSummaryItem[]> {
  const query = new URLSearchParams();
  query.set("year", year.toString());
  query.set("month", month.toString());
  if (accountCode) query.set("account_code", accountCode);
  if (initialBalance !== undefined) query.set("initial_balance", initialBalance.toString());
  return apiRequest<LedgerSummaryItem[]>(`/api/accounting/ledger?${query.toString()}`);
}

export async function downloadAccountingExcel(year: number, month: number): Promise<void> {
  const padded = String(month).padStart(2, "0");
  return downloadAuthenticatedFile(
    `/api/accounting/export/excel?year=${year}&month=${month}`,
    `reporte_contable_p2p_${year}_${padded}.xlsx`
  );
}

export async function downloadAccountingPdf(year: number, month: number): Promise<void> {
  const padded = String(month).padStart(2, "0");
  return downloadAuthenticatedFile(
    `/api/accounting/export/pdf?year=${year}&month=${month}`,
    `reporte_contable_${year}_${padded}.pdf`
  );
}

export async function matchVoucherWithOrder(voucherId: number, orderNumber: string): Promise<any> {
  return apiRequest(`/api/accounting/vouchers/${voucherId}/match`, {
    method: "POST",
    body: JSON.stringify({ order_number: orderNumber }),
  });
}

export async function getLiveBalance(
  year: number,
  month: number,
  initialUsdt: number = 0,
  initialVes: number = 0,
  bankBalances?: Record<string, number>
): Promise<any> {
  const query = new URLSearchParams();
  query.set("year", year.toString());
  query.set("month", month.toString());
  query.set("initial_usdt", initialUsdt.toString());
  query.set("initial_ves", initialVes.toString());
  if (bankBalances && Object.keys(bankBalances).length > 0) {
    query.set("bank_balances_json", JSON.stringify(bankBalances));
  }
  return apiRequest(`/api/accounting/balances/live?${query.toString()}`);
}

export async function reconcileOrphanVouchers(toleranceHours: number = 48): Promise<any> {
  return apiRequest(`/api/accounting/vouchers/reconcile-orphans?tolerance_hours=${toleranceHours}`, {
    method: "POST",
  });
}

export interface ManualVoucherPayload {
  bank_name: string;
  reference_number: string;
  amount_ves: number;
  movement_type: "DEBIT" | "CREDIT";
  payment_method: "PAGO_MOVIL" | "TRANSFER" | "INTERBANK";
  sender_name?: string;
  sender_id?: string;
  bank_fee_ves?: number;
  order_number?: string;
}

export async function createManualVoucher(
  data: ManualVoucherPayload
): Promise<UploadVoucherResponse> {
  return apiRequest<UploadVoucherResponse>("/api/accounting/vouchers/manual", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function uploadVoucherFile(file: File): Promise<UploadVoucherResponse> {

  const formData = new FormData();
  formData.append("file", file);
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${getApiBaseUrl()}/api/accounting/vouchers/upload`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    let detail = "Error al subir comprobante";
    try {
      const errJson = await res.json();
      detail = formatApiErrorDetail(errJson.detail, detail);
    } catch {
      // Ignorar fallo de parseo JSON
    }
    throw new Error(detail);
  }
  return res.json();
}

export type StatementAction =
  | "P2P_MATCH"
  | "P2P_UNMATCHED"
  | "BANK_FEE"
  | "DUPLICATE_EXISTING"
  | "INTERNAL_TRANSFER"
  | "IGNORE";

export interface StatementPreviewRow {
  row_index: number;
  date_vet: string;
  reference_number: string;
  concept: string;
  movement_type: "DEBIT" | "CREDIT";
  amount_ves: number;
  bank_fee_ves: number;
  balance_ves?: number | null;
  balance_ok?: boolean | null;
  balance_discrepancy: number;
  payment_method: string;
  suggested_action: StatementAction;
  matched_order_number?: string | null;
  matched_order_type?: string | null;
  matched_order_crypto?: number | null;
  matched_order_fiat?: number | null;
  match_confidence: number;
  notes: string;
}

export interface StatementAvailableOrder {
  order_number: string;
  trade_type: "BUY" | "SELL" | string;
  fiat_amount: number;
  crypto_amount: number;
  date_vet: string;
}

export interface StatementPreviewResponse {
  bank_name: string;
  file_type: string;
  extraction_method: string;
  detected_columns: string[];
  needs_column_mapping: boolean;
  detected_order: string;
  opening_balance?: number | null;
  closing_balance?: number | null;
  balance_verified: boolean;
  balance_mismatch_count: number;
  total_rows: number;
  p2p_matched_count: number;
  bank_fee_count: number;
  duplicate_count: number;
  unmatched_count: number;
  rows: StatementPreviewRow[];
  warnings: string[];
  available_orders: StatementAvailableOrder[];
}

export interface StatementCommitRowPayload {
  row_index: number;
  date_vet: string;
  reference_number: string;
  concept: string;
  movement_type: "DEBIT" | "CREDIT";
  amount_ves: number;
  payment_method: string;
  action: StatementAction;
  order_number?: string | null;
  bank_fee_ves?: number;
}

export interface StatementCommitResponse {
  status: string;
  bank_name: string;
  created_vouchers: number;
  matched_orders: number;
  bank_fees_recorded: number;
  internal_transfers_recorded: number;
  unmatched_recorded: number;
  ignored_rows: number;
  journal_entries_created: number;
  periods_affected: string[];
}

export async function previewBankStatement(
  file: File,
  options?: {
    bank_name?: string;
    column_mapping?: Record<string, string>;
    year_hint?: number;
  }
): Promise<StatementPreviewResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (options?.bank_name?.trim()) {
    formData.append("bank_name", options.bank_name.trim());
  }
  if (options?.column_mapping && Object.keys(options.column_mapping).length > 0) {
    formData.append("column_mapping_json", JSON.stringify(options.column_mapping));
  }
  if (options?.year_hint) {
    formData.append("year_hint", String(options.year_hint));
  }
  return apiRequest<StatementPreviewResponse>("/api/accounting/statements/preview", {
    method: "POST",
    body: formData,
  });
}

export async function commitBankStatement(data: {
  bank_name: string;
  rows: StatementCommitRowPayload[];
}): Promise<StatementCommitResponse> {
  return apiRequest<StatementCommitResponse>("/api/accounting/statements/commit", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ---------- Terminal de Velas P2P y Predictor Estadístico (SPEC-025) ----------

export type MarketSideMode = "sell" | "buy" | "bank" | "evolucion" | "brecha";
export type MarketTimeframe = "1m" | "5m" | "15m" | "1h" | "4h" | "1D";

export interface MarketCandlePoint {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number | null;
}

export interface MarketLinePoint {
  time: number;
  value: number | null;
}

export interface MarketPercentileBand {
  floor: number;
  ceiling: number;
  coverage: number;
  r_low_pct: number;
  r_high_pct: number;
}

export interface MarketBandBacktest {
  hits: number;
  evaluated: number;
  hit_rate_pct: number;
}

export interface MarketCandlesResponse {
  side: MarketSideMode;
  timeframe: MarketTimeframe;
  bank: string;
  ticket_ves: number;
  candles: MarketCandlePoint[];
  ema9: MarketLinePoint[];
  ema21: MarketLinePoint[];
  rsi14: MarketLinePoint[];
  bcv_series: MarketLinePoint[];
  band: MarketPercentileBand | null;
  mature_days: number;
  samples_total: number;
  bank_options: string[];
  warnings: string[];
}

export interface MarketDepthBucket {
  buy_usdt: number;
  sell_usdt: number;
  top1_share_pct: number;
  imbalance: number;
}

export interface MarketDepthSummary {
  top5: MarketDepthBucket;
  top10: MarketDepthBucket;
  top20: MarketDepthBucket;
  imbalance: number;
}

export interface MarketTicketVwap {
  fillable: boolean;
  vwap_price: number;
  best_price: number;
  slippage_pct: number;
  top_price_covers_ticket: boolean;
  covered_ves: number;
  ads_needed: number;
}

export interface MarketLiquidityAlert {
  detected: boolean;
  ratio_pct: number | null;
  baseline_median_usdt: number | null;
  status: string;
}

export interface MarketBankCell {
  bank: string;
  sell_best: number;
  sell_avg: number;
  buy_best: number;
  buy_avg: number;
  sustained_high_pc: number | null;
  vol_buy: number;
  vol_sell: number;
}

export interface MarketAnalyticsResponse {
  rsi14_current: number | null;
  ema4_vs_ema12_pct: number | null;
  ema5_vs_ema20_pct: number | null;
  brecha_velocity: number | null;
  depth_summary: MarketDepthSummary;
  vwap_buy: MarketTicketVwap;
  vwap_sell: MarketTicketVwap;
  liquidity_alert: MarketLiquidityAlert;
  band: MarketPercentileBand | null;
  band_backtest: MarketBandBacktest | null;
  samples_total: number;
  days_count: number;
  min_prediction_days: number;
  live_bcv: number;
  live_p2p_buy: number;
  live_p2p_sell: number;
  brecha_pct: number;
  banks_snapshot: MarketBankCell[];
  verdict_label: string;
  warnings: string[];
}

export interface MarketCollectResponse {
  captured: boolean;
  cooldown_remaining_s: number;
  message: string;
  snapshot_timestamp?: string | null;
}

export async function getMarketCandles(params: {
  side?: MarketSideMode;
  timeframe?: MarketTimeframe;
  bank?: string;
  ticketVes?: number;
  limit?: number;
  fresh?: boolean;
  signal?: AbortSignal;
} = {}): Promise<MarketCandlesResponse> {
  const query = new URLSearchParams();
  query.set("side", params.side ?? "sell");
  query.set("timeframe", params.timeframe ?? "5m");
  query.set("bank", params.bank ?? "*");
  query.set("ticket_ves", String(params.ticketVes ?? 1_000_000));
  query.set("limit", String(params.limit ?? 240));
  return apiRequest<MarketCandlesResponse>(`/api/market/candles?${query.toString()}`, {
    fresh: params.fresh,
    signal: params.signal,
  });
}

export async function getMarketAnalytics(params: {
  bank?: string;
  ticketVes?: number;
  side?: MarketSideMode;
  fresh?: boolean;
  signal?: AbortSignal;
} = {}): Promise<MarketAnalyticsResponse> {
  const query = new URLSearchParams();
  query.set("bank", params.bank ?? "*");
  query.set("ticket_ves", String(params.ticketVes ?? 1_000_000));
  if (params.side) {
    query.set("side", params.side);
  }
  return apiRequest<MarketAnalyticsResponse>(`/api/market/analytics?${query.toString()}`, {
    fresh: params.fresh,
    signal: params.signal,
  });
}

export async function triggerMarketCollect(params: {
  bank?: string;
  ticketVes?: number;
} = {}): Promise<MarketCollectResponse> {
  const query = new URLSearchParams();
  if (params.bank) query.set("bank", params.bank);
  if (params.ticketVes && params.ticketVes > 0) {
    query.set("ticket_ves", String(params.ticketVes));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiRequest<MarketCollectResponse>(`/api/market/collect${suffix}`, {
    method: "POST",
  });
}
