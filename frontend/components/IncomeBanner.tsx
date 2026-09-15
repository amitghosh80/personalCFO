"use client";

import { useEffect, useState } from "react";
import { getIncomeReviewStatus } from "@/lib/api";

/**
 * Persistent app-wide banner shown when auto-detected income was skipped or left
 * unreviewed (AMI-24). Links back to that import's income review. Dismissal is
 * per-session; the banner returns next session until the income is reviewed.
 */
export default function IncomeBanner() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [count, setCount] = useState(0);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let active = true;
    getIncomeReviewStatus()
      .then((s) => {
        if (!active) return;
        if (s.incomplete && s.job_id) {
          setJobId(s.job_id);
          setCount(s.unreviewed_count);
        }
      })
      .catch(() => {
        /* status unavailable (e.g. backend down) — just don't show the banner */
      });
    return () => {
      active = false;
    };
  }, []);

  if (dismissed || !jobId) return null;

  return (
    <div className="bg-amber-50 border-b border-amber-200">
      <div className="max-w-7xl mx-auto px-6 md:px-10 py-2.5 flex items-center justify-between gap-4">
        <p className="text-sm text-amber-800">
          <span className="font-semibold">Income review incomplete</span> — {count}{" "}
          detected income {count === 1 ? "transaction hasn't" : "transactions haven't"} been
          confirmed, so income figures may be inaccurate.
        </p>
        <div className="flex items-center gap-3 shrink-0">
          <a
            href={`/import/${jobId}/income`}
            className="text-sm font-medium text-amber-900 underline hover:text-amber-950"
          >
            Review now
          </a>
          <button
            onClick={() => setDismissed(true)}
            className="text-amber-500 hover:text-amber-700 text-lg leading-none"
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      </div>
    </div>
  );
}
