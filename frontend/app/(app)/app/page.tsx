"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import FileUploader from "@/components/FileUploader";
import { dismissVitalsPrompt, getFinancialProfile, getMe } from "@/lib/api";
import { track } from "@/lib/track";

type Screen = "loading" | "choice" | "uploader";

export default function ImportPage() {
  const router = useRouter();
  const [screen, setScreen] = useState<Screen>("loading");
  const [dismissing, setDismissing] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function decide() {
      try {
        const [me, profile] = await Promise.all([getMe(), getFinancialProfile()]);
        if (cancelled) return;

        if (!me.vitals_interview_enabled) {
          setScreen("uploader");
          return;
        }
        if (profile.source === "ledger" || profile.source === "user_estimate") {
          // Already past the first-run choice (either imported or completed
          // the interview) — /app is now just the Import page, reached via
          // the nav link or the estimated Profile's CTA. Never bounce away.
          setScreen("uploader");
          return;
        }
        if (me.vitals_prompt_dismissed) {
          setScreen("uploader");
          return;
        }
        track("vitals_prompt_viewed");
        setScreen("choice");
      } catch {
        // A failed eligibility check must never block the existing import
        // page from rendering.
        if (!cancelled) setScreen("uploader");
      }
    }

    decide();
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function chooseImport() {
    track("vitals_path_selected", { path: "import" });
    setDismissing(true);
    try {
      await dismissVitalsPrompt();
    } catch {
      // Non-fatal: worst case the choice screen reappears next visit.
    } finally {
      setScreen("uploader");
      setDismissing(false);
    }
  }

  function chooseInterview() {
    track("vitals_path_selected", { path: "interview" });
    router.push("/profile/vitals");
  }

  function chooseSandbox() {
    track("vitals_path_selected", { path: "sandbox" });
    router.push("/sandbox");
  }

  if (screen === "loading") return null;

  if (screen === "uploader") {
    return (
      <div>
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900">Import Statements</h2>
          <p className="text-gray-500 mt-1">
            Upload your bank or credit card statements. We support CSV exports and PDF statements
            from Chase, Bank of America, Citi, Capital One, American Express, Wells Fargo, and First Tech FCU.
          </p>
        </div>
        <FileUploader />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-8 text-center">
        <h2 className="text-2xl font-bold text-gray-900">See your financial picture today</h2>
        <p className="text-gray-500 mt-1 max-w-xl mx-auto">
          Import a statement for real numbers, or answer four quick questions to get an estimate now.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-3 max-w-3xl mx-auto">
        <button
          type="button"
          onClick={chooseImport}
          disabled={dismissing}
          className="rounded-xl border border-gray-200 bg-white p-6 text-left shadow-sm hover:border-blue-300 hover:shadow-md transition disabled:opacity-60"
        >
          <p className="text-lg font-bold text-gray-900">Import a statement</p>
          <p className="mt-1 text-sm text-gray-500">See what your money is actually doing.</p>
        </button>
        <button
          type="button"
          onClick={chooseInterview}
          className="rounded-xl border border-gray-200 bg-white p-6 text-left shadow-sm hover:border-blue-300 hover:shadow-md transition"
        >
          <p className="text-lg font-bold text-gray-900">Answer a few questions</p>
          <p className="mt-1 text-sm text-gray-500">Get a rough Financial Profile in about 2 minutes.</p>
        </button>
        <button
          type="button"
          onClick={chooseSandbox}
          className="rounded-xl border border-gray-200 bg-white p-6 text-left shadow-sm hover:border-blue-300 hover:shadow-md transition"
        >
          <p className="text-lg font-bold text-gray-900">See a live example</p>
          <p className="mt-1 text-sm text-gray-500">Explore a sample account with five months of real-feeling data.</p>
        </button>
      </div>
      <p className="mt-6 text-center text-xs text-gray-400 max-w-xl mx-auto">
        Your answers are only used to calculate your Financial Profile and can be edited any time. We never ask for
        bank credentials or statement data in the interview.
      </p>
    </div>
  );
}
