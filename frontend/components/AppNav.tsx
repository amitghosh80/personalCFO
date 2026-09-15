"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import DeleteImportsMenuItem from "@/components/DeleteImportsMenuItem";
import FeedbackButton from "@/components/FeedbackButton";
import Wordmark from "@/components/Wordmark";

function ImportIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-5 w-5 shrink-0">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v10m0-10 4 4m-4-4-4 4M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" />
    </svg>
  );
}

function OverviewIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-5 w-5 shrink-0">
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 3h7l3 3v15H7V3Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 9h6M9 13h6M9 17h4" />
    </svg>
  );
}

function TransactionsIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-5 w-5 shrink-0">
      <rect x="3.5" y="4" width="17" height="16" rx="1.5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.5 9.5h17M9 9.5V20" />
    </svg>
  );
}

function ReviewQueueIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-5 w-5 shrink-0">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v16M4 4h11l-2 3 2 3H4" />
    </svg>
  );
}

function AskCfoIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-5 w-5 shrink-0">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 5h16v10H9l-4 4v-4H4V5Z" />
    </svg>
  );
}

const NAV_LINKS = [
  { href: "/app", label: "Import", Icon: ImportIcon },
  { href: "/summary", label: "Overview", Icon: OverviewIcon },
  { href: "/transactions", label: "Transactions", Icon: TransactionsIcon },
  { href: "/uncategorized", label: "Review Queue", Icon: ReviewQueueIcon },
  { href: "/chat", label: "Ask CFO", Icon: AskCfoIcon },
];

const MOBILE_ITEM_CLASS =
  "flex items-center gap-3 w-full px-4 py-3 text-left text-base text-blue-600 hover:bg-gray-50 rounded-lg transition-colors";

const SIDEBAR_UTIL_CLASS =
  "flex items-center gap-3 w-full rounded-lg px-3 py-2 text-left text-sm text-blue-600 hover:bg-blue-50 transition-colors";

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
 * The authenticated app's nav — a persistent left sidebar at md+ and a
 * hamburger/drawer top bar below it. Shared by the (app) layout and, when
 * the visitor is logged in, the /sandbox page — the sandbox is reachable
 * both signed out (via a shared link) and signed in (as the 3rd first-run
 * choice-screen option), and a logged-in visitor needs a way back to their
 * own /app instead of just the demo's own banner.
 */
export default function AppNav({ onLogout }: { onLogout: () => void }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  function sidebarLinkClass(href: string) {
    const active = pathname === href;
    return `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
      active ? "bg-blue-50 text-blue-800 font-medium" : "text-blue-600 hover:bg-blue-50 hover:text-blue-800"
    }`;
  }

  return (
    <>
      <div className="md:hidden bg-white border-b border-gray-200">
        <div className="px-6 py-4 flex items-center justify-between">
          <a href="/">
            <Wordmark />
          </a>
          <button
            onClick={() => setMobileOpen((v) => !v)}
            className="-mr-2 flex h-11 w-11 items-center justify-center text-gray-600 hover:text-gray-900"
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileOpen}
          >
            {mobileOpen ? <CloseIcon /> : <MenuIcon />}
          </button>
        </div>

        {mobileOpen && (
          <div className="border-t border-gray-200 px-2 py-2 flex flex-col">
            {NAV_LINKS.map(({ href, label, Icon }) => (
              <a key={href} href={href} className={MOBILE_ITEM_CLASS}>
                <Icon />
                {label}
              </a>
            ))}
            <FeedbackButton className={MOBILE_ITEM_CLASS} />
            <DeleteImportsMenuItem className={`${MOBILE_ITEM_CLASS} text-gray-500`} />
            <button onClick={onLogout} className={`${MOBILE_ITEM_CLASS} text-gray-500`}>
              Log out
            </button>
          </div>
        )}
      </div>

      <aside className="hidden md:sticky md:top-0 md:flex md:h-screen md:w-60 md:shrink-0 md:flex-col md:overflow-y-auto md:border-r md:border-gray-200 md:bg-white">
        <a href="/" className="px-6 py-6 block">
          <Wordmark />
        </a>
        <nav className="flex-1 flex flex-col gap-1 px-3">
          {NAV_LINKS.map(({ href, label, Icon }) => (
            <a key={href} href={href} className={sidebarLinkClass(href)}>
              <Icon />
              {label}
            </a>
          ))}
        </nav>
        <div className="border-t border-gray-200 px-3 py-4 flex flex-col gap-1">
          <FeedbackButton className={SIDEBAR_UTIL_CLASS} />
          <DeleteImportsMenuItem className={`${SIDEBAR_UTIL_CLASS} text-gray-500`} />
          <button onClick={onLogout} className={`${SIDEBAR_UTIL_CLASS} text-gray-500`}>
            Log out
          </button>
        </div>
      </aside>
    </>
  );
}
