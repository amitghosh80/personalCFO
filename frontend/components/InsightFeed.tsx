"use client";

import { useEffect, useState } from "react";
import { dismissInsight, getInsights } from "@/lib/api";
import type { Insight, InsightFeedResponse, InsightType } from "@/lib/types";

const TYPE_LABELS: Record<InsightType, string> = {
  spending_increase: "Spending Increase",
  spending_decrease: "Spending Decrease",
  income_change: "Income Change",
  recurring_charge: "Recurring Charge",
  duplicate_charge: "Duplicate Charge",
  large_expense: "Large Expense",
  merchant_spike: "Merchant Spike",
  cashflow_risk: "Cashflow Risk",
  transfer_detected: "Transfer Detected",
  subscription_creep: "Subscription Creep",
  top_spending_category: "Top Expense Category",
  category_spike: "Category Spending Spike",
};

const SEV = {
  high: {
    border: "border-red-200",
    header: "bg-red-50",
    badge: "bg-red-100 text-red-700 border border-red-200",
  },
  medium: {
    border: "border-amber-200",
    header: "bg-amber-50",
    badge: "bg-amber-100 text-amber-700 border border-amber-200",
  },
  low: {
    border: "border-blue-200",
    header: "bg-blue-50",
    badge: "bg-blue-100 text-blue-700 border border-blue-200",
  },
};

function formatPeriod(start: string | null, end: string | null): string {
  if (!start) return "";
  const fmt = (s: string) =>
    new Date(s + "T00:00:00").toLocaleString("en-US", { month: "short", year: "numeric" });
  if (!end || start.slice(0, 7) === end.slice(0, 7)) return fmt(start);
  return `${fmt(start)} – ${fmt(end)}`;
}

function ConfChip({ label }: { label: string }) {
  const cls =
    label === "high"
      ? "bg-green-50 text-green-700"
      : label === "medium"
      ? "bg-yellow-50 text-yellow-700"
      : "bg-gray-100 text-gray-500";
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>
      {label.charAt(0).toUpperCase() + label.slice(1)} confidence
    </span>
  );
}

function InsightCard({
  insight,
  onDismiss,
}: {
  insight: Insight;
  onDismiss: () => void;
}) {
  const sev = SEV[insight.severity];
  const period = formatPeriod(insight.time_period_start, insight.time_period_end);

  return (
    <div className={`rounded-xl border overflow-hidden ${sev.border}`}>
      <div className={`px-5 py-4 ${sev.header}`}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${sev.badge}`}>
              {insight.severity.charAt(0).toUpperCase() + insight.severity.slice(1)}
            </span>
            <span className="text-xs text-gray-500 font-medium">
              {TYPE_LABELS[insight.insight_type] ?? insight.insight_type}
            </span>
            {period && <span className="text-xs text-gray-400">{period}</span>}
          </div>
          <button
            onClick={onDismiss}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors shrink-0 mt-0.5"
          >
            Dismiss
          </button>
        </div>
        <h3 className="font-semibold text-gray-900 mt-2 text-base leading-tight">
          {insight.title}
        </h3>
      </div>

      <div className="px-5 py-4 bg-white space-y-3">
        <p className="text-sm text-gray-600 leading-relaxed">{insight.explanation}</p>
        <ConfChip label={insight.confidence_label} />
        <div className="bg-gray-50 rounded-lg px-4 py-3 border border-gray-100">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
            Suggested next step
          </p>
          <p className="text-sm text-gray-700">{insight.suggested_next_step}</p>
        </div>
      </div>
    </div>
  );
}

const SEV_FILTERS = ["all", "high", "medium", "low"] as const;

export default function InsightFeed() {
  const [data, setData] = useState<InsightFeedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sevFilter, setSevFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  useEffect(() => {
    getInsights()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleDismiss = async (id: number) => {
    await dismissInsight(id);
    setData((prev) =>
      prev
        ? {
            ...prev,
            insights: prev.insights.filter((i) => i.id !== id),
            total: prev.total - 1,
            high_severity_count:
              prev.insights.find((i) => i.id === id)?.severity === "high"
                ? prev.high_severity_count - 1
                : prev.high_severity_count,
            medium_severity_count:
              prev.insights.find((i) => i.id === id)?.severity === "medium"
                ? prev.medium_severity_count - 1
                : prev.medium_severity_count,
            low_severity_count:
              prev.insights.find((i) => i.id === id)?.severity === "low"
                ? prev.low_severity_count - 1
                : prev.low_severity_count,
          }
        : prev
    );
  };

  if (loading) return <div className="text-gray-400 text-center py-16">Loading insights…</div>;
  if (error) return <div className="text-red-600 text-center py-16">{error}</div>;
  if (!data) return null;

  const availableTypes = Array.from(new Set(data.insights.map((i) => i.insight_type)));
  const filtered = data.insights.filter(
    (i) =>
      (sevFilter === "all" || i.severity === sevFilter) &&
      (typeFilter === "all" || i.insight_type === typeFilter)
  );

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Insight Feed</h1>
        {data.total > 0 ? (
          <div className="flex gap-3 text-sm">
            {data.high_severity_count > 0 && (
              <span className="text-red-600 font-medium">
                {data.high_severity_count} high
              </span>
            )}
            {data.medium_severity_count > 0 && (
              <span className="text-amber-600 font-medium">
                {data.medium_severity_count} medium
              </span>
            )}
            {data.low_severity_count > 0 && (
              <span className="text-blue-600 font-medium">
                {data.low_severity_count} low
              </span>
            )}
          </div>
        ) : (
          <p className="text-sm text-gray-400">No insights generated yet.</p>
        )}
      </div>

      {/* Filter bar */}
      {data.total > 0 && (
        <div className="flex flex-wrap gap-2 mb-6">
          {SEV_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => setSevFilter(s)}
              className={`text-sm px-3 py-1.5 rounded-full border transition-colors ${
                sevFilter === s
                  ? "bg-gray-900 text-white border-gray-900"
                  : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
              }`}
            >
              {s === "all" ? "All severity" : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
          {availableTypes.length > 1 && (
            <>
              <span className="text-gray-200 self-center select-none">|</span>
              {availableTypes.slice(0, 6).map((t) => (
                <button
                  key={t}
                  onClick={() => setTypeFilter(typeFilter === t ? "all" : t)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    typeFilter === t
                      ? "bg-gray-900 text-white border-gray-900"
                      : "bg-white text-gray-500 border-gray-200 hover:bg-gray-50"
                  }`}
                >
                  {TYPE_LABELS[t as InsightType] ?? t}
                </button>
              ))}
            </>
          )}
        </div>
      )}

      {/* Feed or empty state */}
      {filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400 bg-gray-50 rounded-xl border border-gray-200">
          {data.total === 0
            ? "Not enough data yet — import at least 2 months of statements to unlock your Insight Feed."
            : "No insights match the current filters."}
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((ins) => (
            <InsightCard key={ins.id} insight={ins} onDismiss={() => handleDismiss(ins.id)} />
          ))}
        </div>
      )}
    </div>
  );
}
