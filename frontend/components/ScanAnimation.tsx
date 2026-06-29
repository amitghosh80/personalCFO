"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getTransactions } from "@/lib/api";
import StepNav from "@/components/StepNav";
import type { Transaction, UploadResult } from "@/lib/types";

/**
 * Live import scan (PRD F5). A presentation layer over already-complete F1/F2
 * detection: transaction rows scroll past a fixed detection line and flagged
 * rows (income / large expense / excluded transfer) get an annotation badge.
 * Purely decorative — Income Review is fully populated either way, so Skip and
 * reduced-motion both route straight there with no recompute.
 */

const LARGE_EXPENSE_THRESHOLD = 500; // PRD F5 default (configurable threshold is P1)
const ROW_H = 44;        // px per row
const VISIBLE = 5;       // rows in the viewport
const STEP_MS = 90;      // pace per row
const ANIMATE_CAP = 40;  // bounded duration: animate the first N, fast-forward the rest

type Flag = "income" | "large_expense" | "transfer" | null;

function isMovement(t: Transaction): boolean {
  return (
    t.is_transfer ||
    t.transfer_status === "paired" ||
    t.expense_category === "transfer" ||
    t.expense_category === "credit_card_payment"
  );
}

function flagOf(t: Transaction): Flag {
  if (t.transaction_type === "credit") {
    if (t.is_income_candidate) return "income";
    return isMovement(t) ? "transfer" : null;
  }
  if (isMovement(t)) return "transfer";
  if (t.amount >= LARGE_EXPENSE_THRESHOLD) return "large_expense";
  return null;
}

const BADGE: Record<Exclude<Flag, null>, { label: string; cls: string }> = {
  income: { label: "Income", cls: "bg-green-100 text-green-800" },
  large_expense: { label: "Large expense", cls: "bg-amber-100 text-amber-800" },
  transfer: { label: "Excluded transfer", cls: "bg-blue-100 text-blue-700" },
};

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

export default function ScanAnimation({ jobId }: { jobId: string }) {
  const router = useRouter();
  const [txns, setTxns] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [pos, setPos] = useState(0);          // index currently at the detection line
  const [done, setDone] = useState(false);
  const [reduced, setReduced] = useState(false);
  const advanced = useRef(false);

  const goToReview = () => {
    if (advanced.current) return;
    advanced.current = true;
    router.push(`/import/${jobId}/income`);
  };

  const uploadResult: UploadResult | null = useMemo(() => {
    if (typeof window === "undefined") return null;
    try {
      const raw = sessionStorage.getItem(`upload:${jobId}`);
      return raw ? (JSON.parse(raw) as UploadResult) : null;
    } catch {
      return null;
    }
  }, [jobId]);

  useEffect(() => {
    setReduced(prefersReducedMotion());
    getTransactions(jobId)
      .then(setTxns)
      .catch(() => setTxns([]))
      .finally(() => setLoading(false));
  }, [jobId]);

  // Stepwise scan; bounded by ANIMATE_CAP, then fast-forwards to the end.
  useEffect(() => {
    if (loading || reduced || txns.length === 0) return;
    if (pos >= Math.min(ANIMATE_CAP, txns.length) - 1) {
      const t = setTimeout(() => {
        setPos(txns.length - 1);
        setDone(true);
      }, STEP_MS * 3);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setPos((p) => p + 1), STEP_MS);
    return () => clearTimeout(t);
  }, [pos, loading, reduced, txns.length]);

  // Auto-advance into Income Review shortly after completion.
  useEffect(() => {
    if (!done) return;
    const t = setTimeout(goToReview, 1400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [done]);

  const counts = useMemo(() => {
    const upto = reduced ? txns.length : pos + 1;
    const c = { income: 0, large_expense: 0, transfer: 0 };
    txns.slice(0, upto).forEach((t) => {
      const f = flagOf(t);
      if (f) c[f] += 1;
    });
    return c;
  }, [txns, pos, reduced]);

  if (loading) {
    return <div className="text-gray-500">Scanning your statements…</div>;
  }

  return (
    <div>
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Scanning {txns.length} transactions</h2>
          <p className="text-gray-400 text-sm mt-0.5">Spotting income, large expenses, and transfers</p>
        </div>
        <button onClick={goToReview} className="text-sm text-gray-500 hover:text-gray-800">
          Skip →
        </button>
      </div>

      {/* Live counters */}
      <div className="mb-4 flex gap-3 flex-wrap">
        <Counter label="Income found" value={counts.income} cls="bg-green-50 text-green-700" />
        <Counter label="Large expenses" value={counts.large_expense} cls="bg-amber-50 text-amber-700" />
        <Counter label="Transfers excluded" value={counts.transfer} cls="bg-blue-50 text-blue-700" />
      </div>

      {reduced ? (
        <ReducedList txns={txns} />
      ) : (
        <ScanViewport txns={txns} pos={pos} />
      )}

      {/* Progress through the statement (position, not time) */}
      <div className="mt-4 h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
        <div
          className="h-full bg-blue-500 transition-all duration-100"
          style={{ width: `${txns.length ? ((reduced ? txns.length : pos + 1) / txns.length) * 100 : 100}%` }}
        />
      </div>

      {(done || reduced) && (
        <div className="mt-6 rounded-xl border border-gray-200 bg-white p-5">
          <p className="font-semibold text-gray-900">{txns.length} transactions imported</p>
          {uploadResult && (
            <ul className="mt-3 space-y-1 text-sm">
              {uploadResult.file_results.map((f, i) => (
                <li key={i} className={f.error ? "text-red-600" : "text-gray-600"}>
                  <span className="font-medium">{f.file}:</span>{" "}
                  {f.error
                    ? f.error
                    : `${f.transactions_saved ?? 0} transactions` +
                      `, ${f.duplicate_count ?? 0} duplicates` +
                      `, ${f.ambiguous_count ?? 0} skipped`}
                </li>
              ))}
            </ul>
          )}
          <button
            onClick={goToReview}
            className="mt-4 w-full py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors"
          >
            Continue to income review
          </button>
        </div>
      )}

      <StepNav
        backHref="/"
        backLabel="Upload"
        onNext={goToReview}
        nextLabel="Income review"
      />
    </div>
  );
}

function Counter({ label, value, cls }: { label: string; value: number; cls: string }) {
  return (
    <div className={`rounded-lg px-4 py-2 ${cls}`}>
      <div className="text-xl font-bold tabular-nums">{value}</div>
      <div className="text-xs">{label}</div>
    </div>
  );
}

function Row({ t, active }: { t: Transaction; active: boolean }) {
  const flag = flagOf(t);
  return (
    <div
      className={`flex items-center gap-3 px-4 border-b border-gray-50 transition-colors ${
        active ? "bg-blue-50/60" : ""
      }`}
      style={{ height: ROW_H }}
    >
      <span className="text-xs text-gray-400 w-20 shrink-0">{t.date}</span>
      <span className="text-sm text-gray-700 truncate flex-1">{t.description}</span>
      <span className={`text-sm font-medium ${t.transaction_type === "credit" ? "text-green-700" : "text-gray-700"}`}>
        {t.transaction_type === "credit" ? "+" : "-"}${t.amount.toLocaleString("en-US", { minimumFractionDigits: 2 })}
      </span>
      {active && flag && (
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${BADGE[flag].cls}`}>
          {BADGE[flag].label}
        </span>
      )}
    </div>
  );
}

function ScanViewport({ txns, pos }: { txns: Transaction[]; pos: number }) {
  const offset = pos * ROW_H - Math.floor(VISIBLE / 2) * ROW_H;
  return (
    <div className="relative bg-white border border-gray-200 rounded-xl overflow-hidden" style={{ height: ROW_H * VISIBLE }}>
      {/* Detection line at vertical center */}
      <div
        className="pointer-events-none absolute left-0 right-0 z-10 border-y-2 border-blue-400/40 bg-blue-400/5"
        style={{ top: Math.floor(VISIBLE / 2) * ROW_H, height: ROW_H }}
      />
      <div className="transition-transform duration-100 ease-linear" style={{ transform: `translateY(${-offset}px)` }}>
        {txns.map((t, i) => (
          <Row key={t.id} t={t} active={i === pos} />
        ))}
      </div>
    </div>
  );
}

function ReducedList({ txns }: { txns: Transaction[] }) {
  const flagged = txns.filter((t) => flagOf(t));
  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden divide-y divide-gray-50">
      {flagged.length === 0 ? (
        <div className="px-4 py-6 text-sm text-gray-400">No income, large expenses, or transfers detected.</div>
      ) : (
        flagged.map((t) => <Row key={t.id} t={t} active />)
      )}
    </div>
  );
}
