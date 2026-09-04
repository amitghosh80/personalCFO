"use client";

import { useRouter } from "next/navigation";
import type { DashboardInsight } from "@/lib/types";

export default function InsightsPanel({
  jobId,
  insights,
  layout = "grid",
  onAskMore,
}: {
  jobId?: string;
  insights: DashboardInsight[];
  layout?: "grid" | "scroll";
  // Overrides navigation to the authenticated /chat route — used by the
  // unauthenticated sandbox, which has no /chat page to navigate to.
  onAskMore?: (insight: DashboardInsight) => void;
}) {
  const router = useRouter();

  if (insights.length === 0) return null;

  const askMore = (insight: DashboardInsight) => {
    if (onAskMore) {
      onAskMore(insight);
      return;
    }
    const params = new URLSearchParams({ q: insight.question });
    if (jobId) params.set("job", jobId);
    router.push(`/chat?${params.toString()}`);
  };

  const card = (insight: DashboardInsight, className: string) => (
    <div key={insight.type} className={`rounded-xl border border-gray-200 bg-white p-4 flex flex-col ${className}`}>
      <p className="text-sm font-semibold text-gray-900 mb-1">{insight.title}</p>
      <p className="text-xs text-gray-500 flex-1">{insight.text}</p>
      <button
        onClick={() => askMore(insight)}
        className="mt-3 text-xs font-medium text-blue-600 hover:text-blue-700 text-left"
      >
        Ask me more →
      </button>
    </div>
  );

  return (
    <div className="mb-6">
      {layout === "scroll" ? (
        <div className="flex gap-3 overflow-x-auto pb-1 snap-x snap-mandatory">
          {insights.map((insight) => card(insight, "w-64 shrink-0 snap-start"))}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-3">
          {insights.map((insight) => card(insight, ""))}
        </div>
      )}
      <p className="mt-2 text-[11px] text-gray-400">
        Automated, based on your imported data — not financial advice. Verify before acting.
      </p>
    </div>
  );
}
