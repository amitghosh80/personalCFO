"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getImportSummary } from "@/lib/api";
import StepNav from "@/components/StepNav";
import MonthlyBreakdown from "@/components/MonthlyBreakdown";
import type { ImportSummary as ImportSummaryType } from "@/lib/types";

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

      <div className="mb-6">
        <MonthlyBreakdown
          rows={summary.monthly_breakdown}
          emptyMessage="No transactions found for this import."
        />
      </div>

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
