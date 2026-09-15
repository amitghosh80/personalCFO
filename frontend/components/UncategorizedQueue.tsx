"use client";

import { useEffect, useState } from "react";
import {
  bulkUpdateCategory,
  getTaxonomy,
  getUncategorized,
  getUncategorizedAlert,
  updateCategory,
} from "@/lib/api";
import type { TaxonomyPrimary, UncategorizedAlert, UncategorizedRow } from "@/lib/types";
import CategoryPicker from "./CategoryPicker";

/**
 * Batch review queue for low-confidence / uncategorized transactions (PRD F3).
 * Rows are sorted by amount desc; the user can multi-select and apply one
 * category, or categorize a single row and create a merchant rule.
 */
export default function UncategorizedQueue({ jobId }: { jobId?: string }) {
  const [rows, setRows] = useState<UncategorizedRow[]>([]);
  const [taxonomy, setTaxonomy] = useState<TaxonomyPrimary[]>([]);
  const [alert, setAlert] = useState<UncategorizedAlert | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    return Promise.all([getUncategorized(jobId), getUncategorizedAlert(jobId)])
      .then(([r, a]) => {
        setRows(r);
        setAlert(a);
        setSelected(new Set());
      })
      .catch((e) => setError(e.message));
  }

  useEffect(() => {
    Promise.all([refresh(), getTaxonomy().then((t) => setTaxonomy(t.primaries))])
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function applyToSelected(primary: string, sub: string, createRule: boolean) {
    await bulkUpdateCategory(Array.from(selected), primary, sub, createRule);
    await refresh();
  }

  async function applyToRow(id: number, primary: string, sub: string, createRule: boolean) {
    await updateCategory(id, primary, sub, createRule);
    setEditingId(null);
    await refresh();
  }

  if (loading) return <div className="text-gray-500">Loading review queue…</div>;
  if (error) return <div className="text-red-600">{error}</div>;

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Review queue</h2>
        <p className="text-gray-400 text-sm mt-0.5">
          {rows.length} uncategorized {rows.length === 1 ? "transaction" : "transactions"}, largest first
        </p>
      </div>

      {alert?.over_threshold && alert.message && (
        <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {alert.message}
        </div>
      )}

      {selected.size > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3">
          <span className="text-sm font-medium text-blue-800">{selected.size} selected →</span>
          <CategoryPicker
            primaries={taxonomy}
            saveLabel="Apply to selected"
            onSave={applyToSelected}
          />
        </div>
      )}

      {rows.length === 0 ? (
        <div className="rounded-xl border border-gray-200 bg-white py-16 text-center text-gray-400">
          Nothing to review — everything is categorized. 🎉
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="w-10 px-4 py-3"></th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Date</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Description</th>
                <th className="text-right px-4 py-3 font-medium text-gray-500">Amount</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Category</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.has(r.id)}
                      onChange={() => toggle(r.id)}
                    />
                  </td>
                  <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{r.date}</td>
                  <td className="px-4 py-3 text-gray-800 max-w-xs truncate">{r.description}</td>
                  <td className="px-4 py-3 text-right font-medium text-gray-800 whitespace-nowrap">
                    ${r.amount.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-3">
                    {editingId === r.id ? (
                      <CategoryPicker
                        primaries={taxonomy}
                        onSave={(p, s, rule) => applyToRow(r.id, p, s, rule)}
                        onCancel={() => setEditingId(null)}
                      />
                    ) : (
                      <button
                        onClick={() => setEditingId(r.id)}
                        className="text-sm text-blue-600 hover:underline"
                      >
                        Categorize
                      </button>
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
