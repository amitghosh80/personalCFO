"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import IncomeBanner from "@/components/IncomeBanner";
import AppNav from "@/components/AppNav";
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
    <div className="flex min-h-screen flex-col md:flex-row">
      <AppNav onLogout={handleLogout} />
      <div className="flex flex-1 min-w-0 flex-col">
        <IncomeBanner />
        <main className="flex-1 w-full max-w-7xl mx-auto px-6 md:px-10 py-10">{children}</main>
        <footer className="border-t border-gray-200 mt-10">
          <div className="max-w-7xl mx-auto px-6 md:px-10 py-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs text-gray-400">
            <p>
              personalCFO does not provide financial, tax, or legal advice. Categorization and chat
              answers can be inaccurate — verify anything important against your actual statements.
            </p>
            <div className="flex gap-4 shrink-0">
              <a href="/terms" className="hover:text-gray-600 transition-colors">
                Terms
              </a>
              <a href="/privacy" className="hover:text-gray-600 transition-colors">
                Privacy
              </a>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
