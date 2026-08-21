"use client";

import { Fragment, useEffect, useState } from "react";
import Link from "next/link";
import type { MonthlyRow } from "@/lib/types";

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

export function formatMonth(yyyyMm: string) {
  const [y, m] = yyyyMm.split("-").map(Number);
  return new Date(y, m - 1).toLocaleString("en-US", { month: "short", year: "numeric" });
}

export function fmt(n: number) {
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

const VISIBLE_CATEGORIES = 5;

function IncomeBars({ row }: { row: MonthlyRow }) {
  const cats = row.income_by_category ?? [];
  if (cats.length === 0) return null;
  const max = Math.max(...cats.map((c) => c.amount), 1);
  return (
    <div className="px-5 py-4 space-y-2 border-b border-gray-100">
      <div className="text-xs font-medium uppercase tracking-wide text-gray-400 mb-1">
        Income breakdown
      </div>
      {cats.map((c) => (
        <div key={c.category} className="flex items-center gap-3">
          <div className="w-28 shrink-0 text-sm text-gray-600">
            {c.display} <span className="text-gray-400">({c.count})</span>
          </div>
          <div className="flex-1 h-5 rounded bg-gray-100 overflow-hidden">
            <div
              className="h-full bg-green-500"
              style={{ width: `${Math.max((c.amount / max) * 100, 2)}%` }}
            />
          </div>
          <div className="w-24 shrink-0 text-right text-sm tabular-nums text-gray-700">{fmt(c.amount)}</div>
        </div>
      ))}
    </div>
  );
}

function CategoryBars({ row }: { row: MonthlyRow }) {
  const [showAll, setShowAll] = useState(false);
  const all = row.top_categories ?? [];
  if (all.length === 0) {
    return <div className="px-5 py-3 text-sm text-gray-400">No categorized expenses this month.</div>;
  }
  const cats = showAll ? all : all.slice(0, VISIBLE_CATEGORIES);
  const hiddenCount = all.length - VISIBLE_CATEGORIES;
  const max = Math.max(...all.map((c) => c.amount), 1);
  return (
    <div className="px-5 py-4 space-y-2">
      <div className="text-xs font-medium uppercase tracking-wide text-gray-400 mb-1">
        {showAll ? "All expense categories" : "Top expense categories"}
      </div>
      {cats.map((c) => (
        <Link
          key={c.category}
          href={`/transactions?category=${encodeURIComponent(c.category)}&month=${row.month}`}
          className="flex items-center gap-3 group rounded px-1 -mx-1 hover:bg-gray-100 transition-colors"
          title={`View ${c.display} transactions in ${row.month}`}
        >
          <div className="w-28 shrink-0 text-sm text-gray-600 group-hover:text-blue-700">
            {c.display}
          </div>
          <div className="flex-1 h-5 rounded bg-gray-100 overflow-hidden">
            <div
              className={`h-full ${CATEGORY_COLORS[c.category] ?? "bg-gray-400"}`}
              style={{ width: `${Math.max((c.amount / max) * 100, 2)}%` }}
            />
          </div>
          <div className="w-24 shrink-0 text-right text-sm tabular-nums text-gray-700">{fmt(c.amount)}</div>
        </Link>
      ))}
      {hiddenCount > 0 && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setShowAll((prev) => !prev);
          }}
          className="text-xs font-medium text-blue-600 hover:text-blue-800 px-1 pt-1"
        >
          {showAll ? "Show fewer categories" : `Show all ${all.length} categories (+${hiddenCount} more)`}
        </button>
      )}
    </div>
  );
}

/**
 * Expandable month-by-month income / expenses / net table with per-month top
 * expense-category bars. Shared by the post-import summary (per job) and the
 * whole-ledger "View import" dashboard.
 */
export default function MonthlyBreakdown({
  rows,
  emptyMessage = "No transactions found.",
}: {
  rows: MonthlyRow[];
  emptyMessage?: string;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // Expand every month's category breakdown by default.
  useEffect(() => {
    setExpanded(new Set(rows.map((r) => r.month)));
  }, [rows]);

  const toggle = (month: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(month) ? next.delete(month) : next.add(month);
      return next;
    });

  if (rows.length === 0) {
    return (
      <div className="text-center py-10 text-gray-400 bg-white border border-gray-200 rounded-xl">
        {emptyMessage}
      </div>
    );
  }

  const total = totals(rows);

  return (
    <div className="rounded-xl border border-gray-200 overflow-hidden">
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
                <tr className="hover:bg-gray-50 transition-colors cursor-pointer" onClick={() => toggle(r.month)}>
                  <td className="px-5 py-3 text-gray-700 font-medium">
                    <span className="inline-flex items-center gap-2">
                      <span className={`text-gray-400 transition-transform ${isOpen ? "rotate-90" : ""}`}>▸</span>
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
                      <IncomeBars row={r} />
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
  );
}
