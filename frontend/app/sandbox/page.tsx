"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import ChatInterface from "@/components/ChatInterface";
import FinancialProfile from "@/components/FinancialProfile";
import InsightsPanel from "@/components/InsightsPanel";
import ScanAnimation from "@/components/ScanAnimation";
import SectionCard from "@/components/SectionCard";
import {
  getSandboxFinancialProfile,
  getSandboxInsights,
  getSandboxStarterQuestions,
  getSandboxTransactions,
  sendSandboxChatMessage,
} from "@/lib/api";
import type { DashboardInsight } from "@/lib/types";

type Stage = "scanning" | "ready";

function Banner() {
  return (
    <div className="bg-blue-600 text-white">
      <div className="max-w-5xl mx-auto px-6 py-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <Link href="/" className="text-sm font-bold tracking-tight shrink-0">
          personal<span className="text-blue-200">CFO</span>
        </Link>
        <p className="text-sm flex-1 min-w-0">
          You&apos;re viewing <span className="font-semibold">Jordan</span> — a fictional example account with
          sample data.
        </p>
        <Link href="/signup" className="text-sm font-semibold underline hover:no-underline shrink-0">
          Sign up free to build your own
        </Link>
      </div>
    </div>
  );
}

export default function SandboxPage() {
  const [stage, setStage] = useState<Stage>("scanning");
  const [insights, setInsights] = useState<DashboardInsight[]>([]);
  const [chatQuestion, setChatQuestion] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (stage !== "ready") return;
    getSandboxInsights().then(setInsights).catch(() => {});
  }, [stage]);

  if (stage === "scanning") {
    return (
      <div className="min-h-screen bg-gray-50">
        <Banner />
        <div className="max-w-3xl mx-auto px-6 py-10">
          <p className="mb-4 text-sm text-gray-500">
            This is what importing looks like — here it&apos;s replaying Jordan&apos;s five months of sample
            statements.
          </p>
          <ScanAnimation
            fetchTransactions={getSandboxTransactions}
            onComplete={() => setStage("ready")}
            showUploadSummary={false}
            showStepNav={false}
            autoAdvance={false}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Banner />

      <div className="max-w-5xl mx-auto px-6 py-10 space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Jordan&apos;s Financial Profile</h1>
          <p className="text-gray-500 mt-1">
            34, one checking account and two credit cards — five months of real-feeling transactions, computed
            exactly the way your real ledger would be once you import statements.
          </p>
        </div>

        <InsightsPanel insights={insights} onAskMore={(insight) => setChatQuestion(insight.question)} />

        <FinancialProfile fetchProfile={getSandboxFinancialProfile} />

        <SectionCard
          title="Ask CFO"
          description="Ask Jordan's assistant anything about this sample ledger — real answers, computed live."
          accent="violet"
        >
          <ChatInterface
            sendMessage={sendSandboxChatMessage}
            fetchStarters={getSandboxStarterQuestions}
            initialMessage={chatQuestion}
          />
        </SectionCard>
      </div>
    </div>
  );
}
