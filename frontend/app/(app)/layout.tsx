"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import IncomeBanner from "@/components/IncomeBanner";
import DeleteImportsMenuItem from "@/components/DeleteImportsMenuItem";
import { isAuthenticated, clearToken } from "@/lib/auth";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
    } else {
      setChecked(true);
    }
  }, [router]);

  function handleLogout() {
    clearToken();
    router.push("/login");
  }

  if (!checked) return null;

  return (
    <>
      <IncomeBanner />
      <nav className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <a href="/" className="text-lg font-bold text-gray-900 tracking-tight">
            PersonalCFO
          </a>
          <div className="flex items-center gap-5">
            <a href="/app" className="text-sm text-blue-600 hover:text-blue-800 transition-colors">
              Import
            </a>
            <a href="/summary" className="text-sm text-blue-600 hover:text-blue-800 transition-colors">
              View import
            </a>
            <a href="/transactions" className="text-sm text-blue-600 hover:text-blue-800 transition-colors">
              Transactions
            </a>
            <a href="/uncategorized" className="text-sm text-blue-600 hover:text-blue-800 transition-colors">
              Review Queue
            </a>
            <a href="/chat" className="text-sm text-blue-600 hover:text-blue-800 transition-colors">
              Ask CFO
            </a>
            <a href="/feedback" className="text-sm text-blue-600 hover:text-blue-800 transition-colors">
              Feedback
            </a>
            <DeleteImportsMenuItem />
            <button
              onClick={handleLogout}
              className="text-sm text-gray-500 hover:text-gray-800 transition-colors"
            >
              Log out
            </button>
          </div>
        </div>
      </nav>
      <main className="max-w-5xl mx-auto px-6 py-10">{children}</main>
    </>
  );
}
