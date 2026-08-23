"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getLedgerSummary, getSummaryInsights } from "@/lib/api";
import MonthlyBreakdown from "@/components/MonthlyBreakdown";
import InsightsPanel from "@/components/InsightsPanel";
import FinancialProfile from "@/components/FinancialProfile";
import SectionCard from "@/components/SectionCard";
import type { DashboardInsight, LedgerSummary as LedgerSummaryType } from "@/lib/types";

/**
 * The "View import" dashboard: spending by category, month by month, across
 * every import. Reads /api/summary (whole-ledger), which shares its math with
 * the chat tools so the numbers match askCFO.
 */
export default function LedgerSummary() {
  const [summary, setSummary] = useState<LedgerSummaryType | null>(null);
  const [insights, setInsights] = useState<DashboardInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getLedgerSummary()
      .then(setSummary)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    // Best-effort: proactive insights are progressive enhancement, never block the page.
    getSummaryInsights().then(setInsights).catch(() => {});
  }, []);

  if (loading) return <div className="text-gray-500">Loading summary…</div>;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!summary) return null;

  const empty = summary.total_transactions === 0;

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-1">Spending by month</h2>
        <p className="text-gray-500">
          {summary.total_transactions} transactions across all imports
          {summary.date_range.from && summary.date_range.to
            ? ` · ${summary.date_range.from} → ${summary.date_range.to}`
            : ""}
        </p>
      </div>

      <FinancialProfile />

      {insights.length > 0 && (
        <SectionCard
          title="Recent Insights"
          description="Proactive patterns detected in your latest data."
          accent="violet"
        >
          <InsightsPanel insights={insights} layout="scroll" />
        </SectionCard>
      )}

      <SectionCard
        title="Income, Expenses & Net Cash Flow"
        description="Per-month totals across every import."
        accent="emerald"
      >
        <MonthlyBreakdown
          rows={summary.monthly_breakdown}
          emptyMessage="No transactions imported yet."
        />
        {summary.income_includes_unreviewed && (
          <p className="text-xs text-gray-400 mt-3 px-1">
            * Income includes auto-detected candidates not yet confirmed.
          </p>
        )}
      </SectionCard>

      {empty && (
        <div className="mt-6">
          <Link
            href="/app"
            className="inline-block px-5 py-3 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-700 transition-colors"
          >
            Import a statement
          </Link>
        </div>
      )}
    </div>
  );
}
