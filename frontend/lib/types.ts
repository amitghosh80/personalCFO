export type TransactionType = "debit" | "credit";

export type IncomeCategory = "salary" | "freelance" | "interest" | "rental" | "gig" | "other";

export type ConfidenceLabel = "low" | "medium" | "high";

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
  expense_subcategory: string | null;
  category_source: "rule" | "ai" | "user" | "fallback" | null;
  category_confidence: number | null;
  confidence_label: ConfidenceLabel | null;
  is_transfer: boolean;
  transfer_status: "paired" | "unconfirmed" | null;
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
  already_imported?: boolean;
  existing_job_id?: string | null;
}

export interface UploadResult {
  import_job_id: string;
  file_results: FileResult[];
  total_transactions: number;
  transfers_paired: number;
  transfers_unconfirmed: number;
  // Set when every uploaded file was a duplicate: the import they already live in.
  existing_job_id?: string | null;
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

// Primary keys mirror backend TAXONOMY in expense_categorizer.py.
export type ExpenseCategory =
  | "housing"
  | "utilities"
  | "food_and_drink"
  | "transportation"
  | "travel"
  | "shopping"
  | "entertainment"
  | "subscriptions"
  | "health"
  | "personal_care"
  | "insurance"
  | "debt_payments"
  | "education"
  | "pets"
  | "financial"
  | "taxes"
  | "gifts_donations"
  | "cash"
  | "other"
  | "credit_card_payment"
  | "transfer"
  | "investment";

// ─── Categorization (F3) ──────────────────────────────────────────────────────

export interface TaxonomySub {
  key: string;
  display: string;
}

export interface TaxonomyPrimary {
  key: string;
  display: string;
  is_spending: boolean;
  subcategories: TaxonomySub[];
}

export interface TaxonomyResponse {
  primaries: TaxonomyPrimary[];
}

export interface UncategorizedRow {
  id: number;
  date: string;
  description: string;
  amount: number;
  expense_category: string | null;
  confidence_label: ConfidenceLabel | null;
}

export interface UncategorizedAlert {
  over_threshold: boolean;
  uncategorized_count: number;
  uncategorized_amount: number;
  total_count: number;
  total_spend: number;
  pct_count: number;
  pct_spend: number;
  message: string | null;
}

export interface MerchantRule {
  id: number;
  merchant_pattern: string;
  primary: string;
  subcategory: string;
  display: string;
  created_at: string;
  match_count: number;
}

export interface IncomeCategoryBreakdown {
  category: IncomeCategory | string;
  display: string;
  amount: number;
  count: number;
}

export interface ImportSummary {
  import_job_id: string;
  status: string;
  total_transactions: number;
  monthly_breakdown: MonthlyRow[];
  income_includes_unreviewed: boolean;
  total_income: number;
  income_by_category: IncomeCategoryBreakdown[];
  income_date_range: { from: string | null; to: string | null };
  duplicate_count: number;
  ambiguous_count: number;
  date_range: { from: string | null; to: string | null };
}

// Whole-ledger summary (the "View import" dashboard): same monthly shape as an
// import summary, aggregated across every import.
export interface LedgerSummary {
  total_transactions: number;
  monthly_breakdown: MonthlyRow[];
  income_includes_unreviewed: boolean;
  date_range: { from: string | null; to: string | null };
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface ChatToolUse {
  name: string;
  input: Record<string, unknown>;
}

export interface DataCoverage {
  date_range: { from: string; to: string } | null;
  account_count: number;
  institutions: string[];
  transaction_count: number;
}

export interface ChatResponse {
  answer: string;
  tools_used: ChatToolUse[];
  coverage?: DataCoverage;
}

export interface Observation {
  kind: "summary" | "spending" | "anomaly";
  title: string;
  text: string;
}

export interface DashboardInsight {
  type: string;
  title: string;
  text: string;
  question: string;
}

export type FeedbackCategory = "bug" | "feature" | "general";

export interface FeedbackResponse {
  id: number;
  created_at: string;
}
