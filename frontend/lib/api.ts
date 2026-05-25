import type { FileResult, ImportSummary, Transaction, UploadResult } from "./types";

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

export async function getTransactions(jobId?: string): Promise<Transaction[]> {
  const url = jobId
    ? `${API}/api/transactions?import_job_id=${jobId}`
    : `${API}/api/transactions`;
  const res = await fetch(url);
  return handleResponse<Transaction[]>(res);
}
