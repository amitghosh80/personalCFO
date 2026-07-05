import type {
  ChatMessage,
  ChatResponse,
  ImportSummary,
  MerchantRule,
  Observation,
  TaxonomyResponse,
  Transaction,
  UncategorizedAlert,
  UncategorizedRow,
  UploadResult,
} from "./types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function uploadStatements(files: File[]): Promise<UploadResult> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const res = await fetch(`${API}/api/upload`, { method: "POST", body: form });
  return handleResponse<UploadResult>(res);
}

export async function getIncomeReview(jobId: string): Promise<Transaction[]> {
  const res = await fetch(`${API}/api/import/${jobId}/income-review`);
  return handleResponse<Transaction[]>(res);
}

export async function confirmIncome(
  jobId: string,
  transactionIds: number[],
  confirmed: boolean,
  incomeCategory?: string
): Promise<{ updated: number }> {
  const res = await fetch(`${API}/api/import/${jobId}/income-review`, {
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
  const res = await fetch(`${API}/api/import/${jobId}/summary`);
  return handleResponse<ImportSummary>(res);
}

export async function getLedgerSummary(): Promise<import("./types").LedgerSummary> {
  const res = await fetch(`${API}/api/summary`);
  return handleResponse<import("./types").LedgerSummary>(res);
}

export interface IncomeReviewStatus {
  incomplete: boolean;
  unreviewed_count: number;
  job_id: string | null;
}

export async function getIncomeReviewStatus(): Promise<IncomeReviewStatus> {
  const res = await fetch(`${API}/api/income/review-status`);
  return handleResponse<IncomeReviewStatus>(res);
}

// ─── Categorization (F3) ──────────────────────────────────────────────────────

export async function getTaxonomy(): Promise<TaxonomyResponse> {
  const res = await fetch(`${API}/api/categories/taxonomy`);
  return handleResponse<TaxonomyResponse>(res);
}

export async function updateCategory(
  txnId: number,
  primary: string,
  subcategory: string,
  createRule = false
): Promise<{ updated: number; rule_created: boolean }> {
  const res = await fetch(`${API}/api/categories/transaction/${txnId}`, {
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
  const res = await fetch(`${API}/api/categories/bulk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transaction_ids: transactionIds, primary, subcategory, create_rule: createRule }),
  });
  return handleResponse(res);
}

export async function getUncategorized(jobId?: string): Promise<UncategorizedRow[]> {
  const url = jobId
    ? `${API}/api/categories/uncategorized?import_job_id=${jobId}`
    : `${API}/api/categories/uncategorized`;
  const res = await fetch(url);
  return handleResponse<UncategorizedRow[]>(res);
}

export async function getUncategorizedAlert(jobId?: string): Promise<UncategorizedAlert> {
  const url = jobId
    ? `${API}/api/categories/uncategorized/alert?import_job_id=${jobId}`
    : `${API}/api/categories/uncategorized/alert`;
  const res = await fetch(url);
  return handleResponse<UncategorizedAlert>(res);
}

export async function listRules(): Promise<MerchantRule[]> {
  const res = await fetch(`${API}/api/categories/rules`);
  return handleResponse<MerchantRule[]>(res);
}

export async function deleteRule(ruleId: number): Promise<{ deleted: number }> {
  const res = await fetch(`${API}/api/categories/rules/${ruleId}`, { method: "DELETE" });
  return handleResponse(res);
}

export async function getTransactions(jobId?: string): Promise<Transaction[]> {
  const url = jobId
    ? `${API}/api/transactions?import_job_id=${jobId}`
    : `${API}/api/transactions`;
  const res = await fetch(url);
  return handleResponse<Transaction[]>(res);
}

export async function sendChatMessage(
  question: string,
  history: ChatMessage[]
): Promise<ChatResponse> {
  const res = await fetch(`${API}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history }),
  });
  return handleResponse<ChatResponse>(res);
}

export async function getStarterQuestions(): Promise<string[]> {
  const res = await fetch(`${API}/api/chat/starters`);
  const body = await handleResponse<{ questions: string[] }>(res);
  return body.questions;
}

export async function getObservations(jobId: string): Promise<Observation[]> {
  const res = await fetch(`${API}/api/import/${jobId}/observations`);
  const body = await handleResponse<{ observations: Observation[] }>(res);
  return body.observations;
}
