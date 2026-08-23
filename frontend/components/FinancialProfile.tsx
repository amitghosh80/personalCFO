"use client";

import { useEffect, useState } from "react";
import { getFinancialProfile } from "@/lib/api";
import { fmt, formatMonth } from "@/components/MonthlyBreakdown";
import SectionCard from "@/components/SectionCard";
import type {
  AverageMonthlyBurnPayload,
  AverageMonthlyIncomePayload,
  CommittedMonthlySpendPayload,
  ConfidenceLabel,
  FeesAndInterestPayload,
  FinancialProfile as FinancialProfileType,
  FixedVsDiscretionaryPayload,
  ProfileMetric,
  SavingsRatePayload,
} from "@/lib/types";

function money(n: number, decimals = 0) {
  const sign = n < 0 ? "-" : "";
  return `${sign}$${Math.abs(n).toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

const CONFIDENCE_STYLES: Record<ConfidenceLabel, string> = {
  high: "bg-green-100 text-green-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-gray-200 text-gray-600",
};

function ConfidenceChip({ label }: { label: ConfidenceLabel }) {
  return (
    <span className={`shrink-0 text-[11px] font-medium px-1.5 py-0.5 rounded ${CONFIDENCE_STYLES[label]}`}>
      {label[0].toUpperCase() + label.slice(1)}
    </span>
  );
}

const METRIC_ORDER = [
  "committed_monthly_spend",
  "average_monthly_burn",
  "average_monthly_income",
  "fixed_vs_discretionary",
  "savings_rate",
  "fees_and_interest",
] as const;

type MetricKey = (typeof METRIC_ORDER)[number];

const METRIC_LABELS: Record<MetricKey, string> = {
  committed_monthly_spend: "Committed Monthly Spend",
  average_monthly_burn: "Average Monthly Burn",
  average_monthly_income: "Average Monthly Income",
  fixed_vs_discretionary: "Fixed vs. Discretionary",
  savings_rate: "Savings Rate",
  fees_and_interest: "Fees & Interest Paid",
};

function primaryFigure(key: MetricKey, payload: any): { primary: string; secondary?: string } {
  switch (key) {
    case "committed_monthly_spend": {
      const p = payload as CommittedMonthlySpendPayload;
      return { primary: `${money(p.committed_monthly_total)}/mo`, secondary: `${money(p.committed_annualized_total)}/yr` };
    }
    case "average_monthly_burn": {
      const p = payload as AverageMonthlyBurnPayload;
      return { primary: `${money(p.burn_3mo)}/mo`, secondary: p.burn_6mo != null ? `6mo avg ${money(p.burn_6mo)}` : undefined };
    }
    case "average_monthly_income": {
      const p = payload as AverageMonthlyIncomePayload;
      return { primary: `${money(p.income_3mo)}/mo`, secondary: p.income_6mo != null ? `6mo avg ${money(p.income_6mo)}` : undefined };
    }
    case "fixed_vs_discretionary": {
      const p = payload as FixedVsDiscretionaryPayload;
      return { primary: `${p.fixed_pct.toFixed(0)}% fixed`, secondary: `floor ${money(p.burn_rate_floor)}/mo` };
    }
    case "savings_rate": {
      const p = payload as SavingsRatePayload;
      return { primary: `${(p.savings_rate_3mo * 100).toFixed(0)}%`, secondary: `${money(p.window_net_total)} kept` };
    }
    case "fees_and_interest": {
      const p = payload as FeesAndInterestPayload;
      return { primary: `${money(p.ytd_total)} YTD`, secondary: p.trailing_12mo_total != null ? `${money(p.trailing_12mo_total)}/12mo` : undefined };
    }
  }
}

function DrillDown({ metricKey, payload }: { metricKey: MetricKey; payload: any }) {
  switch (metricKey) {
    case "committed_monthly_spend": {
      const p = payload as CommittedMonthlySpendPayload;
      if (p.commitments.length === 0) return <p className="text-sm text-gray-400">No recurring commitments detected yet.</p>;
      return (
        <ul className="divide-y divide-gray-100">
          {p.commitments.map((c) => (
            <li key={c.merchant + c.next_expected_charge} className="py-2 flex items-center gap-3 text-sm">
              <span className="flex-1 min-w-0 truncate text-gray-700">{c.merchant}</span>
              <span className="shrink-0 text-xs text-gray-400">{c.cadence}</span>
              <span className="shrink-0 w-20 text-right tabular-nums text-gray-700">{fmt(c.amount_per_period)}</span>
            </li>
          ))}
        </ul>
      );
    }
    case "average_monthly_burn": {
      const p = payload as AverageMonthlyBurnPayload;
      return (
        <ul className="divide-y divide-gray-100">
          {p.monthly_series.map((row) => (
            <li key={row.month} className="py-2 flex items-center justify-between text-sm">
              <span className="text-gray-500">{formatMonth(row.month)}</span>
              <span className="tabular-nums text-gray-700">{fmt(row.total_debits)}</span>
            </li>
          ))}
        </ul>
      );
    }
    case "average_monthly_income": {
      const p = payload as AverageMonthlyIncomePayload;
      return (
        <div className="space-y-3">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-gray-400 mb-1">Sources</div>
            <ul className="divide-y divide-gray-100">
              {p.sources.map((s) => (
                <li key={s.source} className="py-2 flex items-center gap-3 text-sm">
                  <span className="flex-1 min-w-0 truncate text-gray-700">{s.source}</span>
                  <span className="shrink-0 text-xs text-gray-400">{s.cadence} · {s.stability}</span>
                  <span className="shrink-0 w-20 text-right tabular-nums text-gray-700">{fmt(s.monthly_avg)}</span>
                </li>
              ))}
            </ul>
          </div>
          {p.by_category.length > 0 && (
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-gray-400 mb-1">By category</div>
              <ul className="divide-y divide-gray-100">
                {p.by_category.map((c) => (
                  <li key={c.income_category} className="py-2 flex items-center justify-between text-sm">
                    <span className="text-gray-500 capitalize">{c.income_category}</span>
                    <span className="tabular-nums text-gray-700">{fmt(c.monthly_avg)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      );
    }
    case "fixed_vs_discretionary": {
      const p = payload as FixedVsDiscretionaryPayload;
      return (
        <ul className="divide-y divide-gray-100">
          {p.fixed_breakdown.map((g) => (
            <li key={g.group} className="py-2 flex items-center justify-between text-sm">
              <span className="text-gray-500">{g.group}</span>
              <span className="tabular-nums text-gray-700">{fmt(g.monthly_avg)}</span>
            </li>
          ))}
        </ul>
      );
    }
    case "savings_rate": {
      const p = payload as SavingsRatePayload;
      return (
        <ul className="divide-y divide-gray-100">
          {p.monthly_series.map((row) => (
            <li key={row.month} className="py-2 flex items-center gap-3 text-sm">
              <span className="flex-1 text-gray-500">{formatMonth(row.month)}</span>
              <span className="tabular-nums text-green-700">{fmt(row.income)}</span>
              <span className="tabular-nums text-red-600">{fmt(row.spend)}</span>
              <span className="w-14 text-right tabular-nums text-gray-700">{(row.rate * 100).toFixed(0)}%</span>
            </li>
          ))}
        </ul>
      );
    }
    case "fees_and_interest": {
      const p = payload as FeesAndInterestPayload;
      if (p.breakdown.length === 0) return <p className="text-sm text-gray-400">No fees or interest detected.</p>;
      return (
        <ul className="divide-y divide-gray-100">
          {p.breakdown.map((b) => (
            <li key={b.sub_type} className="py-2 flex items-center justify-between text-sm">
              <span className="text-gray-500 capitalize">{b.sub_type.replace(/_/g, " ")} ({b.transaction_count})</span>
              <span className="tabular-nums text-gray-700">{fmt(b.ytd_total)}</span>
            </li>
          ))}
        </ul>
      );
    }
  }
}

function Tile({ metricKey, metric }: { metricKey: MetricKey; metric: ProfileMetric<any> }) {
  const [expanded, setExpanded] = useState(false);

  if (metric.status === "insufficient_data") {
    return (
      <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 flex flex-col">
        <p className="text-xs font-semibold text-gray-400 mb-2">{METRIC_LABELS[metricKey]}</p>
        <p className="text-sm text-gray-400 flex-1">{metric.requirement}</p>
      </div>
    );
  }

  const { primary, secondary } = primaryFigure(metricKey, metric.payload);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 flex flex-col">
      <div className="flex items-start justify-between gap-2 mb-1">
        <p className="text-xs font-semibold text-gray-500">{METRIC_LABELS[metricKey]}</p>
        <ConfidenceChip label={metric.confidence_label} />
      </div>
      <p className="text-xl font-bold text-gray-900">{primary}</p>
      {secondary && <p className="text-xs text-gray-400 mb-1">{secondary}</p>}
      <p className="text-xs text-gray-500 flex-1 mt-1">{metric.narrative}</p>
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="mt-3 text-xs font-medium text-blue-600 hover:text-blue-700 text-left"
      >
        {expanded ? "Hide details" : "Show details"} {expanded ? "▲" : "▼"}
      </button>
      {expanded && (
        <div className="mt-2 pt-2 border-t border-gray-100">
          <DrillDown metricKey={metricKey} payload={metric.payload} />
        </div>
      )}
    </div>
  );
}

/**
 * Flow 5: the Financial Profile — evergreen stat tiles at the top of the View
 * Important page. Unlike the episodic Insight Feed, these never dismiss; they
 * recompute from the full ledger on every load.
 */
export default function FinancialProfile() {
  const [profile, setProfile] = useState<FinancialProfileType | null>(null);

  useEffect(() => {
    // Best-effort: the profile module is progressive enhancement, never blocks the page.
    getFinancialProfile().then(setProfile).catch(() => {});
  }, []);

  if (!profile) return null;

  return (
    <SectionCard
      title="Financial Profile"
      description="Standing metrics recomputed from your full ledger after every import."
      accent="blue"
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {METRIC_ORDER.map((key) => (
          <Tile key={key} metricKey={key} metric={profile.metrics[key]} />
        ))}
      </div>
      <p className="mt-3 text-[11px] text-gray-400">
        Automated, based on your imported data — not financial advice. Verify before acting.
      </p>
    </SectionCard>
  );
}
