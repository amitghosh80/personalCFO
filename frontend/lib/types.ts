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

export interface IncomeTransaction {
  id: number;
  date: string;
  description: string;
  amount: number;
  category: string;
  display: string;
}

export interface MonthlyRow {
  month: string;      // "YYYY-MM"
  income: number;
  expenses: number;
  net: number;
  top_categories: CategoryBreakdown[];
  income_transactions: IncomeTransaction[];
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
  result?: Record<string, unknown>;
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
  followups?: string[];
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

// ─── Financial Profile (Flow 5: evergreen metrics) ────────────────────────────

export interface CommitmentOccurrence {
  id: number;
  date: string;
  amount: number;
  description: string;
}

export interface CommitmentDetail {
  merchant: string;
  cadence: string;
  amount_per_period: number;
  monthly_equivalent: number;
  next_expected_charge: string;
  occurrences_detected: number;
  supporting_transaction_ids: number[];
  occurrences: CommitmentOccurrence[];
  confidence: number;
  confidence_label: ConfidenceLabel;
  cadence_ambiguous: boolean;
  category: string;
}

export interface CommittedMonthlySpendPayload {
  committed_monthly_total: number;
  committed_annualized_total: number;
  commitment_count: number;
  commitments: CommitmentDetail[];
}

export interface MonthlyDebitPoint {
  month: string;
  total_debits: number;
  transaction_count: number;
  vs_prev_month_pct: number | null;
  top_categories: CategoryBreakdown[];
}

export interface AverageMonthlyBurnPayload {
  burn_3mo: number;
  burn_6mo: number | null;
  month_to_date: number;
  months_in_window: number;
  variance_ratio: number;
  monthly_series: MonthlyDebitPoint[];
}

export interface IncomeCategoryAvg {
  income_category: string;
  monthly_avg: number;
}

export interface IncomeSource {
  source: string;
  income_category: string;
  cadence: string;
  monthly_avg: number;
  stability: "stable" | "variable";
  supporting_transaction_ids: number[];
}

export interface MonthlyIncomePoint {
  month: string;
  confirmed_income: number;
}

export interface AverageMonthlyIncomePayload {
  income_3mo: number;
  income_6mo: number | null;
  month_to_date: number;
  months_in_window: number;
  used_income_fallback: boolean;
  by_category: IncomeCategoryAvg[];
  sources: IncomeSource[];
  monthly_series: MonthlyIncomePoint[];
}

export interface FixedBreakdownGroup {
  group: string;
  category: string;
  monthly_avg: number;
  transactions: CommitmentOccurrence[];
}

export interface FixedVsDiscretionaryPayload {
  fixed_monthly_avg: number;
  discretionary_monthly_avg: number;
  fixed_pct: number;
  burn_rate_floor: number;
  fixed_breakdown: FixedBreakdownGroup[];
  discretionary_breakdown: FixedBreakdownGroup[];
}

export interface SavingsRateMonthPoint {
  month: string;
  income: number;
  spend: number;
  rate: number;
}

export interface SavingsRatePayload {
  savings_rate_3mo: number;
  window_income_total: number;
  window_spend_total: number;
  window_net_total: number;
  months_in_window: number;
  used_income_fallback: boolean;
  monthly_series: SavingsRateMonthPoint[];
}

export interface FeeBreakdown {
  sub_type: string;
  ytd_total: number;
  transaction_count: number;
  transactions: CommitmentOccurrence[];
}

export interface FeesAndInterestPayload {
  ytd_total: number;
  trailing_12mo_total: number | null;
  breakdown: FeeBreakdown[];
  supporting_transaction_ids: number[];
}

export interface ProfileMetricOk<TPayload> {
  status: "ok";
  confidence: number;
  confidence_label: ConfidenceLabel;
  headline: string;
  narrative: string;
  payload: TPayload;
}

export interface ProfileMetricInsufficient {
  status: "insufficient_data";
  requirement: string;
}

// AMI-66: a metric derived from the Financial Vitals interview instead of
// the ledger. Deliberately shape-distinct from ProfileMetricOk — no
// confidence score/label, and its payload never carries transaction IDs.
export interface ProfileMetricEstimated<TPayload> {
  status: "estimated";
  headline: string;
  narrative: string;
  payload: TPayload;
}

export type ProfileMetric<TPayload> =
  | ProfileMetricOk<TPayload>
  | ProfileMetricInsufficient
  | ProfileMetricEstimated<TPayload>;

export interface EstimatedCommittedMonthlySpendPayload {
  committed_monthly_total: number;
  committed_annualized_total: number;
  rent_or_mortgage_monthly: number;
  car_payment_monthly: number;
}

export interface EstimatedSpendBreakdownItem {
  category: "food_and_dining" | "transportation" | "other";
  monthly_avg: number;
}

export interface EstimatedAverageMonthlyBurnPayload {
  monthly_spend_estimate: number;
  breakdown: EstimatedSpendBreakdownItem[];
}

export interface EstimatedAverageMonthlyIncomePayload {
  take_home_pay_monthly: number;
}

export interface EstimatedFixedVsDiscretionaryPayload {
  fixed_monthly_avg: number;
  discretionary_monthly_avg: number;
  fixed_pct: number;
  discretionary_pct: number;
  commitments_exceed_spend: boolean;
  spend_breakdown: EstimatedSpendBreakdownItem[];
}

export interface EstimatedSavingsRatePayload {
  savings_rate: number;
  take_home_pay_monthly: number;
  monthly_spend_estimate: number;
}

export type FinancialProfileSource = "ledger" | "user_estimate" | "none";

export interface FinancialProfile {
  computed_at: string;
  ledger_months_available: number;
  source: FinancialProfileSource;
  estimated: boolean;
  vitals_completed_at?: string;
  metrics: {
    committed_monthly_spend: ProfileMetric<CommittedMonthlySpendPayload | EstimatedCommittedMonthlySpendPayload>;
    average_monthly_burn: ProfileMetric<AverageMonthlyBurnPayload | EstimatedAverageMonthlyBurnPayload>;
    average_monthly_income: ProfileMetric<AverageMonthlyIncomePayload | EstimatedAverageMonthlyIncomePayload>;
    fixed_vs_discretionary: ProfileMetric<FixedVsDiscretionaryPayload | EstimatedFixedVsDiscretionaryPayload>;
    savings_rate: ProfileMetric<SavingsRatePayload | EstimatedSavingsRatePayload>;
    fees_and_interest: ProfileMetric<FeesAndInterestPayload>;
  };
}

// ─── Financial Vitals Interview (AMI-66) ───────────────────────────────────────

export interface FinancialVitals {
  take_home_pay_monthly: number;
  rent_or_mortgage_monthly: number;
  car_payment_monthly: number;
  food_monthly: number;
  transportation_monthly: number;
  other_monthly: number;
  // Derived by the backend as food + transportation + other. Read-only.
  monthly_spend_estimate: number;
  completed_at: string;
  source: "user_estimate";
}

export interface VitalsInput {
  take_home_pay_monthly: number;
  rent_or_mortgage_monthly: number;
  car_payment_monthly: number;
  food_monthly: number;
  transportation_monthly: number;
  other_monthly: number;
}

export type FeedbackCategory = "bug" | "feature" | "general";

export interface FeedbackResponse {
  id: number;
  created_at: string;
}
