"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getImportSummary } from "@/lib/api";
import type { ImportSummary as ImportSummaryType, MonthlyRow } from "@/lib/types";

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

export default function ImportSummary({ jobId }: { jobId: string }) {
  const router = useRouter();
  const [summary, setSummary] = useState<ImportSummaryType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getImportSummary(jobId)
      .then(setSummary)
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
              {rows.map((r) => (
                <tr key={r.month} className="hover:bg-gray-50 transition-colors">
                  <td className="px-5 py-3 text-gray-700 font-medium">{formatMonth(r.month)}</td>
                  <td className="px-5 py-3 text-right tabular-nums text-green-700">{fmt(r.income)}</td>
                  <td className="px-5 py-3 text-right tabular-nums text-red-600">{fmt(r.expenses)}</td>
                  <td className="px-5 py-3 text-right"><NetCell value={r.net} /></td>
                </tr>
              ))}
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
      <div className="flex gap-3">
        <button
          onClick={() => router.push(`/import/${jobId}/income`)}
          className="px-5 py-3 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors"
        >
          Review Income
        </button>
        <button
          onClick={() => router.push(`/transactions?job=${jobId}`)}
          className="flex-1 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors"
        >
          View Transactions
        </button>
        <button
          onClick={() => router.push("/")}
          className="px-5 py-3 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors"
        >
          Import More
        </button>
      </div>
    </div>
  );
}
