"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { confirmIncome, getIncomeReview } from "@/lib/api";
import { exportToExcel } from "@/lib/export";
import type { IncomeCategory, Transaction } from "@/lib/types";

const CATEGORY_LABELS: Record<IncomeCategory, string> = {
  salary: "Salary / Payroll",
  freelance: "Freelance / Contract",
  interest: "Interest / Dividend",
  rental: "Rental Income",
  gig: "Gig / Platform",
  other: "Other Income",
};

const CATEGORY_COLORS: Record<string, string> = {
  salary: "bg-green-100 text-green-800",
  freelance: "bg-teal-100 text-teal-800",
  interest: "bg-blue-100 text-blue-800",
  rental: "bg-purple-100 text-purple-800",
  gig: "bg-orange-100 text-orange-800",
  other: "bg-gray-100 text-gray-700",
};

interface RowState {
  confirmed: boolean;      // toggled by user
  category: string;
  isDirty: boolean;        // user has made a decision
}

export default function IncomeReview({ jobId }: { jobId: string }) {
  const router = useRouter();
  const [credits, setCredits] = useState<Transaction[]>([]);
  const [rowState, setRowState] = useState<Record<number, RowState>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getIncomeReview(jobId)
      .then((data) => {
        setCredits(data);
        const initial: Record<number, RowState> = {};
        data.forEach((t) => {
          initial[t.id] = {
            confirmed: t.is_income_candidate,   // pre-select auto-detected ones
            category: t.income_category ?? "other",
            isDirty: false,
          };
        });
        setRowState(initial);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [jobId]);

  const toggle = (id: number) => {
    setRowState((prev) => ({
      ...prev,
      [id]: { ...prev[id], confirmed: !prev[id].confirmed, isDirty: true },
    }));
  };

  const setCategory = (id: number, category: string) => {
    setRowState((prev) => ({
      ...prev,
      [id]: { ...prev[id], category, confirmed: true, isDirty: true },
    }));
  };

  const handleConfirm = async () => {
    setSaving(true);
    setError(null);
    try {
      // Batch: confirmed income
      const confirmedIds = credits
        .filter((t) => rowState[t.id]?.confirmed)
        .map((t) => t.id);
      const notIncomeIds = credits
        .filter((t) => !rowState[t.id]?.confirmed && rowState[t.id]?.isDirty)
        .map((t) => t.id);

      // Send updates grouped by category to minimise round-trips
      const byCategory: Record<string, number[]> = {};
      confirmedIds.forEach((id) => {
        const cat = rowState[id]?.category ?? "other";
        byCategory[cat] = [...(byCategory[cat] ?? []), id];
      });

      await Promise.all([
        ...Object.entries(byCategory).map(([cat, ids]) =>
          confirmIncome(jobId, ids, true, cat)
        ),
        notIncomeIds.length
          ? confirmIncome(jobId, notIncomeIds, false)
          : Promise.resolve(),
      ]);

      router.push(`/import/${jobId}/summary`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save. Please try again.");
      setSaving(false);
    }
  };

  const handleSkip = () => router.push(`/import/${jobId}/summary`);

  const handleExport = () => {
    const categoryOverrides = Object.fromEntries(
      Object.entries(rowState).map(([id, s]) => [id, s.category])
    );
    const incomeTxns = credits.filter((t) => t.is_income_candidate);
    const otherTxns = credits.filter((t) => !t.is_income_candidate);
    const sections = [];
    if (incomeTxns.length > 0) {
      sections.push({ name: "Likely Income", transactions: incomeTxns, categoryOverrides });
    }
    if (otherTxns.length > 0) {
      sections.push({ name: "Other Credits", transactions: otherTxns, categoryOverrides });
    }
    exportToExcel(sections, `income-review-${jobId.slice(0, 8)}.xlsx`);
  };

  if (loading) return <div className="text-gray-500">Loading income candidates…</div>;

  const candidates = credits.filter((t) => t.is_income_candidate);
  const otherCredits = credits.filter((t) => !t.is_income_candidate);

  const reviewedCount = credits.filter(
    (t) => rowState[t.id]?.confirmed || rowState[t.id]?.isDirty
  ).length;
  const salaryCandidates = candidates.filter(
    (t) => (rowState[t.id]?.category ?? t.income_category) === "salary"
  );
  const confirmedRows = credits.filter((t) => rowState[t.id]?.confirmed);
  const totalsByType: Record<string, number> = {};
  confirmedRows.forEach((t) => {
    const cat = rowState[t.id]?.category ?? "other";
    totalsByType[cat] = (totalsByType[cat] ?? 0) + t.amount;
  });
  const grandTotal = confirmedRows.reduce((s, t) => s + t.amount, 0);

  const confirmAllSalary = () => {
    setRowState((prev) => {
      const next = { ...prev };
      salaryCandidates.forEach((t) => {
        next[t.id] = { confirmed: true, category: "salary", isDirty: true };
      });
      return next;
    });
  };

  const money = (n: number) => `$${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Review your income</h2>
        <p className="text-gray-500 mt-1">
          We found {candidates.length} potential income transaction
          {candidates.length !== 1 ? "s" : ""}. Confirm or correct each one.
        </p>
        {credits.length > 0 && (
          <p className="text-xs text-gray-400 mt-2">{reviewedCount} of {credits.length} reviewed</p>
        )}
      </div>

      {confirmedRows.length > 0 && (
        <div className="mb-5 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm">
          {Object.entries(totalsByType)
            .sort((a, b) => b[1] - a[1])
            .map(([cat, amt]) => (
              <span key={cat} className="text-green-800">
                {CATEGORY_LABELS[cat as IncomeCategory] ?? cat}: <span className="font-semibold">{money(amt)}</span>
              </span>
            ))}
          <span className="text-green-900 font-bold">Total: {money(grandTotal)}</span>
        </div>
      )}

      {error && (
        <p className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {error}
        </p>
      )}

      {credits.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          No credit transactions found in this import.
        </div>
      ) : (
        <div className="space-y-6">
          {candidates.length > 0 && (
            <div>
              {salaryCandidates.length >= 3 && (
                <button
                  onClick={confirmAllSalary}
                  className="mb-3 text-sm px-3 py-1.5 rounded-lg border border-green-300 text-green-700 hover:bg-green-50 transition-colors"
                >
                  ✓ Confirm all salary/payroll ({salaryCandidates.length})
                </button>
              )}
              <Section
                title="Likely Income"
                subtitle="Auto-detected — deselect anything that isn't actually income"
                transactions={candidates}
                rowState={rowState}
                onToggle={toggle}
                onCategory={setCategory}
              />
            </div>
          )}
          {otherCredits.length > 0 && (
            <Section
              title="Other Credits"
              subtitle="Transfers, refunds, and cashback — select any that are actually income"
              transactions={otherCredits}
              rowState={rowState}
              onToggle={toggle}
              onCategory={setCategory}
            />
          )}
        </div>
      )}

      <div className="mt-8 flex gap-3 flex-wrap">
        <button
          onClick={handleConfirm}
          disabled={saving}
          className="flex-1 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 disabled:opacity-40 transition-colors"
        >
          {saving ? "Saving…" : "Confirm & Continue"}
        </button>
        {credits.length > 0 && (
          <button
            onClick={handleExport}
            className="px-5 py-3 text-gray-700 border border-gray-300 rounded-xl hover:bg-gray-50 transition-colors flex items-center gap-2 shrink-0"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
            Export Excel
          </button>
        )}
        <button
          onClick={handleSkip}
          className="px-6 py-3 text-gray-600 border border-gray-300 rounded-xl hover:bg-gray-50 transition-colors shrink-0"
        >
          Skip for now
        </button>
      </div>
    </div>
  );
}

function Section({
  title,
  subtitle,
  transactions,
  rowState,
  onToggle,
  onCategory,
}: {
  title: string;
  subtitle: string;
  transactions: Transaction[];
  rowState: Record<number, RowState>;
  onToggle: (id: number) => void;
  onCategory: (id: number, cat: string) => void;
}) {
  return (
    <div>
      <div className="mb-3">
        <h3 className="font-semibold text-gray-800">{title}</h3>
        <p className="text-xs text-gray-400">{subtitle}</p>
      </div>
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden divide-y divide-gray-100">
        {transactions.map((t) => {
          const state = rowState[t.id];
          if (!state) return null;
          return (
            <div
              key={t.id}
              onClick={() => onToggle(t.id)}
              className={`flex items-center gap-4 px-5 py-4 cursor-pointer transition-colors ${
                state.confirmed ? "bg-green-50" : "hover:bg-gray-50"
              }`}
            >
              <input
                type="checkbox"
                checked={state.confirmed}
                onChange={() => onToggle(t.id)}
                onClick={(e) => e.stopPropagation()}
                className="w-4 h-4 accent-blue-600 shrink-0"
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{t.description}</p>
                <p className="text-xs text-gray-400 mt-0.5">{t.date}</p>
              </div>
              <span className="text-sm font-semibold text-green-700 shrink-0">
                +${t.amount.toLocaleString("en-US", { minimumFractionDigits: 2 })}
              </span>
              {state.confirmed && (
                <select
                  value={state.category}
                  onChange={(e) => { e.stopPropagation(); onCategory(t.id, e.target.value); }}
                  onClick={(e) => e.stopPropagation()}
                  className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white text-gray-700 shrink-0"
                >
                  {Object.entries(CATEGORY_LABELS).map(([val, label]) => (
                    <option key={val} value={val}>{label}</option>
                  ))}
                </select>
              )}
              {!state.confirmed && state.category && (
                <span className={`text-xs px-2 py-1 rounded-full shrink-0 ${CATEGORY_COLORS[state.category] ?? "bg-gray-100 text-gray-600"}`}>
                  {CATEGORY_LABELS[state.category as IncomeCategory] ?? state.category}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
