export type TransactionType = "debit" | "credit";

export type IncomeCategory = "salary" | "interest" | "rental" | "gig" | "other";

export interface Transaction {
  id: number;
  import_job_id: string;
  date: string;
  description: string;
  amount: number;
  transaction_type: TransactionType;
  currency: string;
  institution: string | null;
  account_last4: string | null;
  is_income_candidate: boolean;
  income_category: IncomeCategory | null;
  income_confirmed: boolean | null;
  is_ambiguous: boolean;
  is_duplicate: boolean;
}

export interface FileResult {
  file: string;
  error?: string;
  institution?: string | null;
  institution_confidence_pct?: number;
  transactions_found?: number;
  transactions_saved?: number;
  date_range?: { from: string; to: string };
  total_credits?: number;
  total_debits?: number;
  income_candidates_count?: number;
  duplicate_count?: number;
  ambiguous_count?: number;
  warnings?: string[];
}

export interface UploadResult {
  import_job_id: string;
  file_results: FileResult[];
  total_transactions: number;
  status: string;
}

export interface ImportSummary {
  import_job_id: string;
  status: string;
  total_transactions: number;
  total_credits: number;
  total_debits: number;
  net_cash_flow: number;
  confirmed_income: number;
  confirmed_income_count: number;
  unreviewed_income_count: number;
  duplicate_count: number;
  ambiguous_count: number;
  date_range: { from: string | null; to: string | null };
}
