"use client";

import { useMemo, useState } from "react";
import type { TaxonomyPrimary } from "@/lib/types";

/**
 * Two-level category selector (primary → subcategory) with an optional
 * "apply to all future from this merchant" rule toggle. Used for inline edits
 * in the transaction table and for the uncategorized review queue.
 */
export default function CategoryPicker({
  primaries,
  initialPrimary,
  initialSub,
  showRuleToggle = true,
  saveLabel = "Save",
  onSave,
  onCancel,
}: {
  primaries: TaxonomyPrimary[];
  initialPrimary?: string | null;
  initialSub?: string | null;
  showRuleToggle?: boolean;
  saveLabel?: string;
  onSave: (primary: string, subcategory: string, createRule: boolean) => void;
  onCancel?: () => void;
}) {
  const [primary, setPrimary] = useState(initialPrimary || primaries[0]?.key || "");
  const subs = useMemo(
    () => primaries.find((p) => p.key === primary)?.subcategories ?? [],
    [primaries, primary]
  );
  const [sub, setSub] = useState(initialSub || subs[0]?.key || "");
  const [createRule, setCreateRule] = useState(false);

  function onPrimaryChange(next: string) {
    setPrimary(next);
    const firstSub = primaries.find((p) => p.key === next)?.subcategories[0]?.key ?? "other";
    setSub(firstSub);
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        value={primary}
        onChange={(e) => onPrimaryChange(e.target.value)}
        className="px-2 py-1 text-sm border border-gray-200 rounded-md bg-white"
      >
        {primaries.map((p) => (
          <option key={p.key} value={p.key}>{p.display}</option>
        ))}
      </select>
      <select
        value={sub}
        onChange={(e) => setSub(e.target.value)}
        className="px-2 py-1 text-sm border border-gray-200 rounded-md bg-white"
      >
        {subs.map((s) => (
          <option key={s.key} value={s.key}>{s.display}</option>
        ))}
      </select>
      {showRuleToggle && (
        <label className="flex items-center gap-1 text-xs text-gray-500">
          <input
            type="checkbox"
            checked={createRule}
            onChange={(e) => setCreateRule(e.target.checked)}
          />
          Apply to this merchant
        </label>
      )}
      <button
        onClick={() => onSave(primary, sub, createRule)}
        className="px-3 py-1 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
      >
        {saveLabel}
      </button>
      {onCancel && (
        <button
          onClick={onCancel}
          className="px-2 py-1 text-sm text-gray-500 hover:text-gray-700"
        >
          Cancel
        </button>
      )}
    </div>
  );
}
