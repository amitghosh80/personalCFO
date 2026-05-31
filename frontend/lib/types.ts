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
  expense_category: ExpenseCategory | null;
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

export interface CategoryBreakdown {
  category: ExpenseCategory | string;
  display: string;
  amount: number;
}

export interface MonthlyRow {
  month: string;      // "YYYY-MM"
  income: number;
  expenses: number;
  net: number;
  top_categories: CategoryBreakdown[];
}

export type ExpenseCategory =
  | "dining"
  | "groceries"
  | "subscriptions"
  | "entertainment"
  | "gas_auto"
  | "travel"
  | "healthcare"
  | "utilities"
  | "housing"
  | "shopping"
  | "other";

export type InsightType =
  | "spending_increase"
  | "spending_decrease"
  | "income_change"
  | "recurring_charge"
  | "duplicate_charge"
  | "large_expense"
  | "merchant_spike"
  | "cashflow_risk"
  | "transfer_detected"
  | "subscription_creep"
  | "top_spending_category"
  | "category_spike";

export type Severity = "low" | "medium" | "high";
export type ConfidenceLabel = "low" | "medium" | "high";

export interface Insight {
  id: number;
  import_job_id: string;
  insight_type: InsightType;
  title: string;
  explanation: string;
  severity: Severity;
  confidence: number;
  confidence_label: ConfidenceLabel;
  time_period_start: string | null;
  time_period_end: string | null;
  supporting_transaction_ids: number[];
  suggested_next_step: string;
  is_dismissed: boolean;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface InsightFeedResponse {
  insights: Insight[];
  total: number;
  high_severity_count: number;
  medium_severity_count: number;
  low_severity_count: number;
}

export interface ImportSummary {
  import_job_id: string;
  status: string;
  total_transactions: number;
  monthly_breakdown: MonthlyRow[];
  income_includes_unreviewed: boolean;
  duplicate_count: number;
  ambiguous_count: number;
  date_range: { from: string | null; to: string | null };
}
