import type {
  ChatMessage,
  ChatResponse,
  DashboardInsight,
  FeedbackCategory,
  FeedbackResponse,
  FinancialProfile,
  ImportSummary,
  MerchantRule,
  Observation,
  TaxonomyResponse,
  Transaction,
  UncategorizedAlert,
  UncategorizedRow,
  UploadResult,
} from "./types";
import { clearToken, getToken } from "./auth";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// Attaches the bearer token to every request and bounces to /login on 401
// (expired/invalid session) so a stale token never renders a blank/broken page.
async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API}${path}`, { ...options, headers });
  if (res.status === 401 && typeof window !== "undefined") {
    clearToken();
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
  }
  return res;
}

// ─── Auth ───────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: number;
  email: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export async function signup(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse<AuthResponse>(res);
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse<AuthResponse>(res);
}

export async function signInWithGoogle(credential: string): Promise<AuthResponse> {
  const res = await fetch(`${API}/api/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential }),
  });
  return handleResponse<AuthResponse>(res);
}

export async function forgotPassword(email: string): Promise<{ message: string }> {
  const res = await fetch(`${API}/api/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  return handleResponse<{ message: string }>(res);
}

export async function resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
  const res = await fetch(`${API}/api/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  return handleResponse<{ message: string }>(res);
}

export async function getMe(): Promise<AuthUser> {
  const res = await apiFetch("/api/auth/me");
  return handleResponse<AuthUser>(res);
}

export async function uploadStatements(files: File[]): Promise<UploadResult> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const res = await apiFetch("/api/upload", { method: "POST", body: form });
  return handleResponse<UploadResult>(res);
}

export async function getIncomeReview(jobId: string): Promise<Transaction[]> {
  const res = await apiFetch(`/api/import/${jobId}/income-review`);
  return handleResponse<Transaction[]>(res);
}

export async function confirmIncome(
  jobId: string,
  transactionIds: number[],
  confirmed: boolean,
  incomeCategory?: string
): Promise<{ updated: number }> {
  const res = await apiFetch(`/api/import/${jobId}/income-review`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      transaction_ids: transactionIds,
      confirmed,
      income_category: incomeCategory ?? null,
    }),
  });
  return handleResponse<{ updated: number }>(res);
}

export async function getImportSummary(jobId: string): Promise<ImportSummary> {
  const res = await apiFetch(`/api/import/${jobId}/summary`);
  return handleResponse<ImportSummary>(res);
}

export async function getLedgerSummary(): Promise<import("./types").LedgerSummary> {
  const res = await apiFetch("/api/summary");
  return handleResponse<import("./types").LedgerSummary>(res);
}

export interface IncomeReviewStatus {
  incomplete: boolean;
  unreviewed_count: number;
  job_id: string | null;
}

export async function getIncomeReviewStatus(): Promise<IncomeReviewStatus> {
  const res = await apiFetch("/api/income/review-status");
  return handleResponse<IncomeReviewStatus>(res);
}

// ─── Categorization (F3) ──────────────────────────────────────────────────────

export async function getTaxonomy(): Promise<TaxonomyResponse> {
  const res = await apiFetch("/api/categories/taxonomy");
  return handleResponse<TaxonomyResponse>(res);
}

export async function updateCategory(
  txnId: number,
  primary: string,
  subcategory: string,
  createRule = false
): Promise<{ updated: number; rule_created: boolean }> {
  const res = await apiFetch(`/api/categories/transaction/${txnId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ primary, subcategory, create_rule: createRule }),
  });
  return handleResponse(res);
}

export async function bulkUpdateCategory(
  transactionIds: number[],
  primary: string,
  subcategory: string,
  createRule = false
): Promise<{ updated: number; rule_created: boolean }> {
  const res = await apiFetch("/api/categories/bulk", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transaction_ids: transactionIds, primary, subcategory, create_rule: createRule }),
  });
  return handleResponse(res);
}

export async function getUncategorized(jobId?: string): Promise<UncategorizedRow[]> {
  const url = jobId
    ? `/api/categories/uncategorized?import_job_id=${jobId}`
    : "/api/categories/uncategorized";
  const res = await apiFetch(url);
  return handleResponse<UncategorizedRow[]>(res);
}

export async function getUncategorizedAlert(jobId?: string): Promise<UncategorizedAlert> {
  const url = jobId
    ? `/api/categories/uncategorized/alert?import_job_id=${jobId}`
    : "/api/categories/uncategorized/alert";
  const res = await apiFetch(url);
  return handleResponse<UncategorizedAlert>(res);
}

export async function listRules(): Promise<MerchantRule[]> {
  const res = await apiFetch("/api/categories/rules");
  return handleResponse<MerchantRule[]>(res);
}

export async function deleteRule(ruleId: number): Promise<{ deleted: number }> {
  const res = await apiFetch(`/api/categories/rules/${ruleId}`, { method: "DELETE" });
  return handleResponse(res);
}

export async function getTransactions(jobId?: string): Promise<Transaction[]> {
  const url = jobId
    ? `/api/transactions?import_job_id=${jobId}`
    : "/api/transactions";
  const res = await apiFetch(url);
  return handleResponse<Transaction[]>(res);
}

export async function sendChatMessage(
  question: string,
  history: ChatMessage[]
): Promise<ChatResponse> {
  const res = await apiFetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history }),
  });
  return handleResponse<ChatResponse>(res);
}

export async function getStarterQuestions(): Promise<string[]> {
  const res = await apiFetch("/api/chat/starters");
  const body = await handleResponse<{ questions: string[] }>(res);
  return body.questions;
}

export async function getObservations(jobId: string): Promise<Observation[]> {
  const res = await apiFetch(`/api/import/${jobId}/observations`);
  const body = await handleResponse<{ observations: Observation[] }>(res);
  return body.observations;
}

export async function getDashboardInsights(jobId: string): Promise<DashboardInsight[]> {
  const res = await apiFetch(`/api/import/${jobId}/dashboard-insights`);
  const body = await handleResponse<{ insights: DashboardInsight[] }>(res);
  return body.insights;
}

export async function getSummaryInsights(): Promise<DashboardInsight[]> {
  const res = await apiFetch(`/api/summary/insights`);
  const body = await handleResponse<{ insights: DashboardInsight[] }>(res);
  return body.insights;
}

export async function getFinancialProfile(): Promise<FinancialProfile> {
  const res = await apiFetch(`/api/financial-profile`);
  return handleResponse<FinancialProfile>(res);
}

// ─── Account data ───────────────────────────────────────────────────────────

export interface ClearDataResult {
  transactions_deleted: number;
  import_jobs_deleted: number;
  insights_deleted: number;
}

export async function clearAllData(): Promise<ClearDataResult> {
  const res = await apiFetch("/api/data", { method: "DELETE" });
  return handleResponse<ClearDataResult>(res);
}

// ─── Feedback ───────────────────────────────────────────────────────────────

export async function submitFeedback(
  category: FeedbackCategory,
  message: string,
  pageUrl?: string
): Promise<FeedbackResponse> {
  const res = await apiFetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category, message, page_url: pageUrl ?? null }),
  });
  return handleResponse<FeedbackResponse>(res);
}
