"use client";

import { useRouter } from "next/navigation";
import type { DashboardInsight } from "@/lib/types";

export default function InsightsPanel({
  jobId,
  insights,
}: {
  jobId?: string;
  insights: DashboardInsight[];
}) {
  const router = useRouter();

  if (insights.length === 0) return null;

  const askMore = (insight: DashboardInsight) => {
    const params = new URLSearchParams({ q: insight.question });
    if (jobId) params.set("job", jobId);
    router.push(`/chat?${params.toString()}`);
  };

  return (
    <div className="mb-6 grid gap-3 sm:grid-cols-3">
      {insights.map((insight) => (
        <div
          key={insight.type}
          className="rounded-xl border border-gray-200 bg-white p-4 flex flex-col"
        >
          <p className="text-sm font-semibold text-gray-900 mb-1">{insight.title}</p>
          <p className="text-xs text-gray-500 flex-1">{insight.text}</p>
          <button
            onClick={() => askMore(insight)}
            className="mt-3 text-xs font-medium text-blue-600 hover:text-blue-700 text-left"
          >
            Ask me more →
          </button>
        </div>
      ))}
    </div>
  );
}
