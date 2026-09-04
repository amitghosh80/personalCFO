"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import DeleteImportsMenuItem from "@/components/DeleteImportsMenuItem";
import FeedbackButton from "@/components/FeedbackButton";

const NAV_LINKS = [
  { href: "/app", label: "Import" },
  { href: "/summary", label: "View import" },
  { href: "/profile", label: "Profile" },
  { href: "/transactions", label: "Transactions" },
  { href: "/uncategorized", label: "Review Queue" },
  { href: "/chat", label: "Ask CFO" },
];

const MOBILE_ITEM_CLASS =
  "block w-full px-4 py-3 text-left text-base text-blue-600 hover:bg-gray-50 rounded-lg transition-colors";

function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-6 w-6">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5M3.75 17.25h16.5" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-6 w-6">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  );
}

/**
 * The authenticated app's top nav (hamburger + drawer below md). Shared by
 * the (app) layout and, when the visitor is logged in, the /sandbox page —
 * the sandbox is reachable both signed out (via a shared link) and signed
 * in (as the 3rd first-run choice-screen option), and a logged-in visitor
 * needs a way back to their own /app instead of just the demo's own banner.
 */
export default function AppNav({ onLogout }: { onLogout: () => void }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  return (
    <nav className="bg-white border-b border-gray-200">
      <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
        <a href="/" className="text-lg font-bold text-gray-900 tracking-tight">
          personal<span className="text-blue-600">CFO</span>
        </a>
        <div className="hidden md:flex items-center gap-5">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
            >
              {link.label}
            </a>
          ))}
          <FeedbackButton />
          <DeleteImportsMenuItem />
          <button onClick={onLogout} className="text-sm text-gray-500 hover:text-gray-800 transition-colors">
            Log out
          </button>
        </div>
        <button
          onClick={() => setMobileOpen((v) => !v)}
          className="md:hidden -mr-2 flex h-11 w-11 items-center justify-center text-gray-600 hover:text-gray-900"
          aria-label={mobileOpen ? "Close menu" : "Open menu"}
          aria-expanded={mobileOpen}
        >
          {mobileOpen ? <CloseIcon /> : <MenuIcon />}
        </button>
      </div>

      {mobileOpen && (
        <div className="md:hidden border-t border-gray-200 px-2 py-2 flex flex-col">
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} className={MOBILE_ITEM_CLASS}>
              {link.label}
            </a>
          ))}
          <FeedbackButton className={MOBILE_ITEM_CLASS} />
          <DeleteImportsMenuItem className={`${MOBILE_ITEM_CLASS} text-gray-500`} />
          <button onClick={onLogout} className={`${MOBILE_ITEM_CLASS} text-gray-500`}>
            Log out
          </button>
        </div>
      )}
    </nav>
  );
}
