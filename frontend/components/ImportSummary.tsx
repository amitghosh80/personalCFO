"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getImportSummary } from "@/lib/api";
import type { ImportSummary as ImportSummaryType } from "@/lib/types";

function StatCard({ label, value, sub, color = "text-gray-900" }: {
  label: string; value: string; sub?: string; color?: string;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl px-5 py-4">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

function fmt(n: number) {
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2 });
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

  const netPositive = summary.net_cash_flow >= 0;

  return (
    <div>
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-2xl">✅</span>
          <h2 className="text-2xl font-bold text-gray-900">Import Complete</h2>
        </div>
        <p className="text-gray-500">
          {summary.total_transactions} transactions imported
          {summary.date_range.from && summary.date_range.to
            ? ` · ${summary.date_range.from} → ${summary.date_range.to}`
            : ""}
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
        <StatCard label="Total Credits" value={fmt(summary.total_credits)} color="text-green-700" />
        <StatCard label="Total Debits" value={fmt(summary.total_debits)} color="text-red-600" />
        <StatCard
          label="Net Cash Flow"
          value={fmt(Math.abs(summary.net_cash_flow))}
          sub={netPositive ? "net positive" : "net negative"}
          color={netPositive ? "text-green-700" : "text-red-600"}
        />
        <StatCard
          label="Confirmed Income"
          value={fmt(summary.confirmed_income)}
          sub={`${summary.confirmed_income_count} transactions`}
          color="text-blue-700"
        />
        {summary.unreviewed_income_count > 0 && (
          <StatCard
            label="Unreviewed Income"
            value={`${summary.unreviewed_income_count}`}
            sub="candidates not yet confirmed"
            color="text-amber-600"
          />
        )}
        {summary.duplicate_count > 0 && (
          <StatCard
            label="Duplicates Flagged"
            value={`${summary.duplicate_count}`}
            sub="may appear in another file"
            color="text-orange-600"
          />
        )}
        {summary.ambiguous_count > 0 && (
          <StatCard
            label="Ambiguous Items"
            value={`${summary.ambiguous_count}`}
            sub="rows that could not be parsed"
            color="text-gray-500"
          />
        )}
      </div>

      {summary.unreviewed_income_count > 0 && (
        <div className="mb-6 bg-amber-50 border border-amber-200 rounded-xl px-5 py-4 flex items-start gap-3">
          <span className="text-xl mt-0.5">⚠️</span>
          <div>
            <p className="font-medium text-amber-800">Income review incomplete</p>
            <p className="text-sm text-amber-700 mt-0.5">
              {summary.unreviewed_income_count} potential income transaction
              {summary.unreviewed_income_count !== 1 ? "s were" : " was"} not reviewed.
              Go back to confirm them for accurate reporting.
            </p>
            <button
              onClick={() => router.push(`/import/${jobId}/income`)}
              className="mt-2 text-sm font-medium text-amber-800 underline"
            >
              Review income →
            </button>
          </div>
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={() => router.push(`/transactions?job=${jobId}`)}
          className="flex-1 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors"
        >
          View Transactions
        </button>
        <button
          onClick={() => router.push("/")}
          className="px-6 py-3 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors"
        >
          Import More
        </button>
      </div>
    </div>
  );
}
