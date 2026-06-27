"use client";

import { useEffect, useMemo, useState } from "react";
import { getTaxonomy, getTransactions, updateCategory } from "@/lib/api";
import type { TaxonomyPrimary, Transaction } from "@/lib/types";
import CategoryPicker from "./CategoryPicker";

const INCOME_LABELS: Record<string, string> = {
  salary: "Salary",
  freelance: "Freelance",
  interest: "Interest",
  rental: "Rental",
  gig: "Gig",
  other: "Other Income",
};

// Keys mirror backend PRIMARY_DISPLAY in expense_categorizer.py.
const EXPENSE_LABELS: Record<string, string> = {
  housing: "Housing",
  utilities: "Utilities",
  food_and_drink: "Food & Drink",
  transportation: "Transportation",
  travel: "Travel",
  shopping: "Shopping",
  entertainment: "Entertainment",
  subscriptions: "Subscriptions",
  health: "Health & Medical",
  personal_care: "Personal Care",
  insurance: "Insurance",
  debt_payments: "Loans & Debt",
  education: "Education & Childcare",
  pets: "Pets",
  financial: "Fees & Financial",
  taxes: "Taxes & Government",
  gifts_donations: "Gifts & Donations",
  cash: "Cash & ATM",
  other: "Other",
  credit_card_payment: "Credit Card Payment",
  transfer: "Transfers",
  investment: "Investments & Savings",
};

const EXPENSE_COLORS: Record<string, string> = {
  housing: "bg-amber-50 text-amber-700",
  utilities: "bg-yellow-50 text-yellow-700",
  food_and_drink: "bg-orange-50 text-orange-700",
  transportation: "bg-slate-100 text-slate-600",
  travel: "bg-sky-50 text-sky-700",
  shopping: "bg-indigo-50 text-indigo-700",
  entertainment: "bg-pink-50 text-pink-700",
  subscriptions: "bg-purple-50 text-purple-700",
  health: "bg-red-50 text-red-700",
  personal_care: "bg-rose-50 text-rose-700",
  insurance: "bg-teal-50 text-teal-700",
  debt_payments: "bg-stone-100 text-stone-700",
  education: "bg-blue-50 text-blue-700",
  pets: "bg-lime-50 text-lime-700",
  financial: "bg-zinc-100 text-zinc-700",
  taxes: "bg-red-100 text-red-800",
  gifts_donations: "bg-fuchsia-50 text-fuchsia-700",
  cash: "bg-green-50 text-green-700",
  other: "bg-gray-100 text-gray-500",
  credit_card_payment: "bg-gray-100 text-gray-500",
  transfer: "bg-gray-100 text-gray-500",
  investment: "bg-cyan-50 text-cyan-700",
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
  const [taxonomy, setTaxonomy] = useState<TaxonomyPrimary[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);

  useEffect(() => {
    getTransactions(jobId)
      .then(setTransactions)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    getTaxonomy().then((t) => setTaxonomy(t.primaries)).catch(() => {});
  }, [jobId]);

  async function saveCategory(t: Transaction, primary: string, sub: string, createRule: boolean) {
    await updateCategory(t.id, primary, sub, createRule);
    setTransactions((prev) =>
      prev.map((x) =>
        x.id === t.id
          ? { ...x, expense_category: primary as Transaction["expense_category"], expense_subcategory: sub, category_source: "user", confidence_label: "high" }
          : x
      )
    );
    setEditingId(null);
  }

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
                    {editingId === t.id ? (
                      <CategoryPicker
                        primaries={taxonomy}
                        initialPrimary={t.expense_category}
                        initialSub={t.expense_subcategory}
                        onSave={(p, s, rule) => saveCategory(t, p, s, rule)}
                        onCancel={() => setEditingId(null)}
                      />
                    ) : (
                      <div className="flex gap-1 flex-wrap items-center">
                        {t.transaction_type === "debit" && t.expense_category && t.expense_category !== "other" && (
                          <Badge
                            label={EXPENSE_LABELS[t.expense_category] ?? t.expense_category}
                            color={EXPENSE_COLORS[t.expense_category] ?? "bg-gray-100 text-gray-500"}
                          />
                        )}
                        {t.transaction_type === "debit" && t.confidence_label === "low" && (
                          <Badge label="Review?" color="bg-amber-100 text-amber-700" />
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
                        {t.transfer_status === "unconfirmed" && (
                          <Badge label="Likely transfer?" color="bg-blue-50 text-blue-700" />
                        )}
                        {t.is_duplicate && (
                          <Badge label="Duplicate?" color="bg-orange-100 text-orange-700" />
                        )}
                        {t.is_ambiguous && (
                          <Badge label="Ambiguous" color="bg-gray-100 text-gray-600" />
                        )}
                        {t.transaction_type === "debit" && (
                          <button
                            onClick={() => setEditingId(t.id)}
                            className="text-xs text-gray-400 hover:text-blue-600"
                            title="Edit category"
                          >
                            ✎
                          </button>
                        )}
                      </div>
                    )}
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
