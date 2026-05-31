"use client";

import { useEffect, useMemo, useState } from "react";
import { getTransactions } from "@/lib/api";
import type { Transaction } from "@/lib/types";

const INCOME_LABELS: Record<string, string> = {
  salary: "Salary",
  interest: "Interest",
  rental: "Rental",
  gig: "Gig",
  other: "Other Income",
};

const EXPENSE_LABELS: Record<string, string> = {
  dining: "Dining",
  groceries: "Groceries",
  subscriptions: "Subscriptions",
  entertainment: "Entertainment",
  gas_auto: "Gas & Auto",
  travel: "Travel",
  healthcare: "Healthcare",
  utilities: "Utilities",
  housing: "Housing",
  shopping: "Shopping",
  other: "Other",
};

const EXPENSE_COLORS: Record<string, string> = {
  dining: "bg-orange-50 text-orange-700",
  groceries: "bg-emerald-50 text-emerald-700",
  subscriptions: "bg-purple-50 text-purple-700",
  entertainment: "bg-pink-50 text-pink-700",
  gas_auto: "bg-slate-100 text-slate-600",
  travel: "bg-sky-50 text-sky-700",
  healthcare: "bg-red-50 text-red-700",
  utilities: "bg-yellow-50 text-yellow-700",
  housing: "bg-amber-50 text-amber-700",
  shopping: "bg-indigo-50 text-indigo-700",
  other: "bg-gray-100 text-gray-500",
};

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span className={`inline-block text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>
      {label}
    </span>
  );
}

export default function TransactionTable({ jobId }: { jobId?: string }) {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<"all" | "debit" | "credit">("all");
  const [sortDir, setSortDir] = useState<"desc" | "asc">("desc");

  useEffect(() => {
    getTransactions(jobId)
      .then(setTransactions)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [jobId]);

  const filtered = useMemo(() => {
    let rows = transactions;
    if (typeFilter !== "all") rows = rows.filter((t) => t.transaction_type === typeFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      rows = rows.filter(
        (t) =>
          t.description.toLowerCase().includes(q) ||
          (t.institution ?? "").toLowerCase().includes(q)
      );
    }
    return [...rows].sort((a, b) => {
      const d = a.date < b.date ? -1 : a.date > b.date ? 1 : 0;
      return sortDir === "desc" ? -d : d;
    });
  }, [transactions, typeFilter, search, sortDir]);

  if (loading) return <div className="text-gray-500">Loading transactions…</div>;
  if (error) return <div className="text-red-600">{error}</div>;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Transactions</h2>
          <p className="text-gray-400 text-sm mt-0.5">
            {filtered.length} of {transactions.length} shown
          </p>
        </div>
        <a href="/" className="text-sm text-blue-600 hover:underline">+ Import more</a>
      </div>

      <div className="flex gap-3 mb-4 flex-wrap">
        <input
          type="text"
          placeholder="Search description or institution…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 min-w-48 px-4 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as typeof typeFilter)}
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white"
        >
          <option value="all">All types</option>
          <option value="credit">Credits only</option>
          <option value="debit">Debits only</option>
        </select>
        <button
          onClick={() => setSortDir((d) => (d === "desc" ? "asc" : "desc"))}
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white hover:bg-gray-50"
        >
          Date {sortDir === "desc" ? "↓" : "↑"}
        </button>
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400">No transactions match your filters.</div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Date</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Description</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Institution</th>
                <th className="text-right px-4 py-3 font-medium text-gray-500">Amount</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Tags</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((t) => (
                <tr key={t.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{t.date}</td>
                  <td className="px-4 py-3 text-gray-800 max-w-xs truncate">{t.description}</td>
                  <td className="px-4 py-3 text-gray-400 whitespace-nowrap">
                    {t.institution ?? "—"}
                  </td>
                  <td className={`px-4 py-3 text-right font-medium whitespace-nowrap ${
                    t.transaction_type === "credit" ? "text-green-700" : "text-gray-800"
                  }`}>
                    {t.transaction_type === "credit" ? "+" : "-"}$
                    {t.amount.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1 flex-wrap">
                      {t.transaction_type === "debit" && t.expense_category && t.expense_category !== "other" && (
                        <Badge
                          label={EXPENSE_LABELS[t.expense_category] ?? t.expense_category}
                          color={EXPENSE_COLORS[t.expense_category] ?? "bg-gray-100 text-gray-500"}
                        />
                      )}
                      {t.income_confirmed === true && t.income_category && (
                        <Badge
                          label={INCOME_LABELS[t.income_category] ?? t.income_category}
                          color="bg-green-100 text-green-800"
                        />
                      )}
                      {t.is_income_candidate && t.income_confirmed === null && (
                        <Badge label="Unreviewed" color="bg-amber-100 text-amber-700" />
                      )}
                      {t.is_duplicate && (
                        <Badge label="Duplicate?" color="bg-orange-100 text-orange-700" />
                      )}
                      {t.is_ambiguous && (
                        <Badge label="Ambiguous" color="bg-gray-100 text-gray-600" />
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
