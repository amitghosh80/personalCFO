"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import AppNav from "@/components/AppNav";
import ChatInterface from "@/components/ChatInterface";
import FinancialProfile from "@/components/FinancialProfile";
import InsightsPanel from "@/components/InsightsPanel";
import ScanAnimation from "@/components/ScanAnimation";
import SectionCard from "@/components/SectionCard";
import Wordmark from "@/components/Wordmark";
import { clearToken, isAuthenticated } from "@/lib/auth";
import {
  getSandboxFinancialProfile,
  getSandboxInsights,
  getSandboxStarterQuestions,
  getSandboxTransactions,
  sendSandboxChatMessage,
} from "@/lib/api";
import type { DashboardInsight } from "@/lib/types";

type Stage = "scanning" | "ready";

// Signed-out visitor (shared link, or previously the landing page hero):
// no account to return to, so pitch signup instead.
function GuestBanner() {
  return (
    <div className="bg-blue-600 text-white">
      <div className="max-w-5xl mx-auto px-6 py-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <Link href="/" className="shrink-0 order-1">
          <Wordmark className="h-7 rounded bg-white/90 px-1.5 py-0.5" />
        </Link>
        <Link
          href="/signup"
          className="text-sm font-semibold underline hover:no-underline shrink-0 order-2 sm:order-3"
        >
          Sign up free to build your own
        </Link>
        <p className="text-sm order-3 sm:order-2 basis-full sm:basis-auto sm:flex-1 sm:min-w-0">
          You&apos;re viewing <span className="font-semibold">Jordan</span> — a fictional example account with
          sample data.
        </p>
      </div>
    </div>
  );
}

// Logged-in visitor (reached via the /app first-run choice screen's "See a
// live example" option): show the real app nav so they can get back to
// their own account, plus a slim notice so the sample data isn't mistaken
// for their own.
function DemoNotice() {
  return (
    <div className="bg-blue-50 border-b border-blue-100">
      <div className="max-w-5xl mx-auto px-6 py-2 text-sm text-blue-800">
        You&apos;re viewing <span className="font-semibold">Jordan</span> — a fictional example account with
        sample data.{" "}
        <Link href="/app" className="font-medium underline hover:no-underline">
          Back to your data
        </Link>
      </div>
    </div>
  );
}

export default function SandboxPage() {
  const router = useRouter();
  const [authed, setAuthed] = useState(false);
  const [stage, setStage] = useState<Stage>("scanning");
  const [insights, setInsights] = useState<DashboardInsight[]>([]);
  const [chatQuestion, setChatQuestion] = useState<string | undefined>(undefined);

  useEffect(() => {
    setAuthed(isAuthenticated());
  }, []);

  useEffect(() => {
    if (stage !== "ready") return;
    getSandboxInsights().then(setInsights).catch(() => {});
  }, [stage]);

  function handleLogout() {
    clearToken();
    router.push("/login");
  }

  const banner = authed ? (
    <>
      <AppNav onLogout={handleLogout} />
      <DemoNotice />
    </>
  ) : (
    <GuestBanner />
  );

  if (stage === "scanning") {
    return (
      <div className="min-h-screen bg-gray-50">
        {banner}
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
      {banner}

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
