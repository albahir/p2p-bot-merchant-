/**
 * Cliente de API tipado para comunicarse con FastAPI.
 */

function getApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  if (typeof window !== "undefined" && window.location?.hostname) {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://127.0.0.1:8000";
}

export interface User {
  id: number;
  username: string;
  full_name?: string | null;
  email?: string | null;
  role: "ADMIN" | "TRADER" | "INVITADO";
  telegram_id?: string | null;
  google_sheet_id?: string | null;
  permission_source?: string;
  telegram_linked?: boolean;
  has_security_question?: boolean;
  has_recovery_key?: boolean;
  binance_api_configured?: boolean;
  binance_key_type?: "HMAC" | "Ed25519" | string | null;
  google_sheet_configured?: boolean;
  is_active: boolean;
  created_at: string;
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

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const isPublicEndpoint =
    endpoint.startsWith("/api/spreads/") ||
    endpoint.startsWith("/api/auth/login") ||
    endpoint.startsWith("/api/auth/register") ||
    endpoint.startsWith("/api/auth/recover-") ||
    endpoint.startsWith("/api/auth/reset-password");

  if (token && !isPublicEndpoint && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${getApiBaseUrl()}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (
      response.status === 401 &&
      typeof window !== "undefined" &&
      !endpoint.startsWith("/api/auth/")
    ) {
      localStorage.removeItem("p2p_token");
      localStorage.removeItem("p2p_user");
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

  return response.json();
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
    localStorage.removeItem("p2p_token");
    localStorage.removeItem("p2p_user");
    window.location.href = "/login";
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
  email?: string;
  telegram_id?: string;
  google_sheet_id?: string;
  security_question?: string;
  security_answer?: string;
}

export interface RecoveryOptions {
  has_telegram: boolean;
  has_security_question: boolean;
  security_question?: string | null;
  has_recovery_key: boolean;
  is_locked: boolean;
}

export type RecoveryMethod = "telegram_otp" | "security_question" | "recovery_key";

export interface RecoveryProfileUpdateData {
  full_name?: string;
  email?: string;
  security_question?: string;
  security_answer?: string;
  regenerate_recovery_key?: boolean;
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

export async function recoverPassword(username: string): Promise<{
  success: boolean;
  message: string;
  has_telegram: boolean;
  debug_code?: string;
}> {
  return apiRequest("/api/auth/recover-password", {
    method: "POST",
    body: JSON.stringify({ username }),
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

export async function getSheetsSettings(): Promise<GoogleSheetsConfigResponse> {
  return apiRequest<GoogleSheetsConfigResponse>("/api/settings/sheets");
}

export async function saveSheetsSettings(data: {
  google_sheet_id: string | null;
  google_auth_type?: "SERVICE_ACCOUNT" | "OAUTH2";
}): Promise<GoogleSheetsConfigResponse> {
  return apiRequest<GoogleSheetsConfigResponse>("/api/settings/sheets", {
    method: "POST",
    body: JSON.stringify({
      google_sheet_id: data.google_sheet_id,
      google_auth_type: data.google_auth_type || "SERVICE_ACCOUNT",
    }),
  });
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
  return apiRequest<GoogleSheetsConfigResponse>("/api/settings/sheets/oauth/callback", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function saveGoogleOAuthClientConfig(data: {
  client_id: string;
  client_secret: string;
  redirect_uri?: string;
}): Promise<GoogleSheetsConfigResponse> {
  return apiRequest<GoogleSheetsConfigResponse>("/api/settings/sheets/oauth/credentials", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function disconnectGoogleOAuth(): Promise<GoogleSheetsConfigResponse> {
  return apiRequest<GoogleSheetsConfigResponse>("/api/settings/sheets/oauth/disconnect", {
    method: "POST",
  });
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
  initialVes: number = 0
): Promise<any> {
  const query = new URLSearchParams();
  query.set("year", year.toString());
  query.set("month", month.toString());
  query.set("initial_usdt", initialUsdt.toString());
  query.set("initial_ves", initialVes.toString());
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
