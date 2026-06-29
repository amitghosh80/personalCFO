"use client";

import { Fragment, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getImportSummary } from "@/lib/api";
import StepNav from "@/components/StepNav";
import type { ImportSummary as ImportSummaryType, MonthlyRow } from "@/lib/types";

// Keys mirror backend TAXONOMY primaries in expense_categorizer.py.
const CATEGORY_COLORS: Record<string, string> = {
  housing: "bg-orange-400",
  utilities: "bg-cyan-500",
  food_and_drink: "bg-rose-400",
  transportation: "bg-amber-500",
  travel: "bg-sky-400",
  shopping: "bg-indigo-400",
  entertainment: "bg-fuchsia-400",
  subscriptions: "bg-violet-400",
  health: "bg-emerald-400",
  personal_care: "bg-pink-400",
  insurance: "bg-teal-400",
  debt_payments: "bg-stone-500",
  education: "bg-blue-400",
  pets: "bg-lime-500",
  financial: "bg-zinc-400",
  taxes: "bg-red-500",
  gifts_donations: "bg-fuchsia-500",
  cash: "bg-green-500",
  other: "bg-gray-400",
  credit_card_payment: "bg-gray-400",
  transfer: "bg-gray-400",
  investment: "bg-cyan-400",
};

function formatMonth(yyyyMm: string) {
  const [y, m] = yyyyMm.split("-").map(Number);
  return new Date(y, m - 1).toLocaleString("en-US", { month: "short", year: "numeric" });
}

function fmt(n: number) {
  return "$" + Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2 });
}

function NetCell({ value }: { value: number }) {
  const positive = value >= 0;
  return (
    <span className={`font-semibold tabular-nums ${positive ? "text-green-700" : "text-red-600"}`}>
      {positive ? "+" : "−"}{fmt(value)}
    </span>
  );
}

function totals(rows: MonthlyRow[]) {
  return rows.reduce(
    (acc, r) => ({ income: acc.income + r.income, expenses: acc.expenses + r.expenses, net: acc.net + r.net }),
    { income: 0, expenses: 0, net: 0 }
  );
}

function CategoryBars({ row }: { row: MonthlyRow }) {
  const cats = row.top_categories ?? [];
  if (cats.length === 0) {
    return <div className="px-5 py-3 text-sm text-gray-400">No categorized expenses this month.</div>;
  }
  const max = Math.max(...cats.map((c) => c.amount), 1);
  return (
    <div className="px-5 py-4 space-y-2">
      <div className="text-xs font-medium uppercase tracking-wide text-gray-400 mb-1">
        Top expense categories
      </div>
      {cats.map((c) => (
        <div key={c.category} className="flex items-center gap-3">
          <div className="w-28 shrink-0 text-sm text-gray-600">{c.display}</div>
          <div className="flex-1 h-5 rounded bg-gray-100 overflow-hidden">
            <div
              className={`h-full ${CATEGORY_COLORS[c.category] ?? "bg-gray-400"}`}
              style={{ width: `${Math.max((c.amount / max) * 100, 2)}%` }}
            />
          </div>
          <div className="w-24 shrink-0 text-right text-sm tabular-nums text-gray-700">{fmt(c.amount)}</div>
        </div>
      ))}
    </div>
  );
}

export default function ImportSummary({ jobId }: { jobId: string }) {
  const router = useRouter();
  const [summary, setSummary] = useState<ImportSummaryType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (month: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(month) ? next.delete(month) : next.add(month);
      return next;
    });

  useEffect(() => {
    getImportSummary(jobId)
      .then((s) => {
        setSummary(s);
        // Show every month's category breakdown by default
        setExpanded(new Set(s.monthly_breakdown.map((r) => r.month)));
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [jobId]);

  if (loading) return <div className="text-gray-500">Loading summary…</div>;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!summary) return null;

  const rows = summary.monthly_breakdown;
  const total = totals(rows);

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-1">Import Complete</h2>
        <p className="text-gray-500">
          {summary.total_transactions} transactions imported
          {summary.date_range.from && summary.date_range.to
            ? ` · ${summary.date_range.from} → ${summary.date_range.to}`
            : ""}
        </p>
      </div>

      {/* Monthly table */}
      {rows.length > 0 ? (
        <div className="mb-6 rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200 text-left">
                <th className="px-5 py-3 font-medium text-gray-500">Month</th>
                <th className="px-5 py-3 font-medium text-gray-500 text-right">Income</th>
                <th className="px-5 py-3 font-medium text-gray-500 text-right">Expenses</th>
                <th className="px-5 py-3 font-medium text-gray-500 text-right">Net Cash Flow</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {rows.map((r) => {
                const isOpen = expanded.has(r.month);
                return (
                  <Fragment key={r.month}>
                    <tr
                      className="hover:bg-gray-50 transition-colors cursor-pointer"
                      onClick={() => toggle(r.month)}
                    >
                      <td className="px-5 py-3 text-gray-700 font-medium">
                        <span className="inline-flex items-center gap-2">
                          <span
                            className={`text-gray-400 transition-transform ${isOpen ? "rotate-90" : ""}`}
                          >
                            ▸
                          </span>
                          {formatMonth(r.month)}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-right tabular-nums text-green-700">{fmt(r.income)}</td>
                      <td className="px-5 py-3 text-right tabular-nums text-red-600">{fmt(r.expenses)}</td>
                      <td className="px-5 py-3 text-right"><NetCell value={r.net} /></td>
                    </tr>
                    {isOpen && (
                      <tr className="bg-gray-50/60">
                        <td colSpan={4} className="border-t border-gray-100 p-0">
                          <CategoryBars row={r} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="bg-gray-50 border-t border-gray-200 font-semibold">
                <td className="px-5 py-3 text-gray-700">Total</td>
                <td className="px-5 py-3 text-right tabular-nums text-green-700">{fmt(total.income)}</td>
                <td className="px-5 py-3 text-right tabular-nums text-red-600">{fmt(total.expenses)}</td>
                <td className="px-5 py-3 text-right"><NetCell value={total.net} /></td>
              </tr>
            </tfoot>
          </table>
        </div>
      ) : (
        <div className="mb-6 text-center py-10 text-gray-400 bg-white border border-gray-200 rounded-xl">
          No transactions found for this import.
        </div>
      )}

      {/* Footnote when income includes unreviewed candidates */}
      {summary.income_includes_unreviewed && (
        <p className="text-xs text-gray-400 -mt-4 mb-5 px-1">
          * Income includes auto-detected candidates not yet confirmed. Go back to income review for accuracy.
        </p>
      )}

      {/* Metadata pills */}
      {(summary.duplicate_count > 0 || summary.ambiguous_count > 0) && (
        <div className="flex flex-wrap gap-2 mb-6">
          {summary.duplicate_count > 0 && (
            <span className="text-xs px-3 py-1.5 rounded-full bg-orange-50 text-orange-700 border border-orange-200">
              {summary.duplicate_count} duplicate{summary.duplicate_count !== 1 ? "s" : ""} flagged
            </span>
          )}
          {summary.ambiguous_count > 0 && (
            <span className="text-xs px-3 py-1.5 rounded-full bg-gray-100 text-gray-600 border border-gray-200">
              {summary.ambiguous_count} row{summary.ambiguous_count !== 1 ? "s" : ""} could not be parsed
            </span>
          )}
        </div>
      )}

      {/* Actions */}
      <StepNav
        className="mt-0"
        backHref={`/import/${jobId}/income`}
        backLabel="Income review"
        onNext={() => router.push(`/transactions?job=${jobId}`)}
        nextLabel="View Transactions"
      >
        <button
          onClick={() => router.push(`/chat?job=${jobId}`)}
          className="px-5 py-3 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors"
        >
          Ask CFO
        </button>
        <button
          onClick={() => router.push("/app")}
          className="px-5 py-3 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors"
        >
          Import More
        </button>
      </StepNav>
    </div>
  );
}
