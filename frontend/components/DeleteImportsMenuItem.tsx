"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { clearAllData } from "@/lib/api";

export default function DeleteImportsMenuItem({ className }: { className?: string } = {}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClear() {
    setClearing(true);
    setError(null);
    try {
      await clearAllData();
      // Per-import upload summaries are cached client-side; drop them so a
      // stale summary can't be read back after the ledger is wiped.
      Object.keys(sessionStorage)
        .filter((k) => k.startsWith("upload:"))
        .forEach((k) => sessionStorage.removeItem(k));
      setOpen(false);
      router.push("/app");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to clear data. Please try again.");
    } finally {
      setClearing(false);
    }
  }

  return (
    <>
      <button
        onClick={() => {
          setError(null);
          setOpen(true);
        }}
        className={className ?? "text-sm text-gray-500 hover:text-red-600 transition-colors"}
      >
        Delete previous imports
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-lg">
            <h3 className="text-sm font-semibold text-gray-900">Delete previous imports?</h3>
            <p className="mt-2 text-sm text-gray-600">
              This permanently deletes every imported statement, transaction, and insight from your
              account. This cannot be undone.
            </p>
            {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
            <div className="mt-5 flex justify-end gap-3">
              <button
                onClick={() => setOpen(false)}
                disabled={clearing}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleClear}
                disabled={clearing}
                className="px-4 py-2 text-sm font-semibold text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
              >
                {clearing ? "Deleting…" : "Yes, delete everything"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
