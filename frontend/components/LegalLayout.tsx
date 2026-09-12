import Link from "next/link";
import Wordmark from "@/components/Wordmark";

export default function LegalLayout({
  title,
  lastUpdated,
  children,
}: {
  title: string;
  lastUpdated: string;
  children: React.ReactNode;
}) {
  return (
    <div className="text-gray-900">
      <header className="sticky top-0 z-50 bg-white/90 backdrop-blur border-b border-gray-200">
        <nav className="max-w-3xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="text-lg">
            <Wordmark />
          </Link>
          <Link href="/" className="text-sm text-gray-600 hover:text-gray-900 transition-colors">
            Back to home
          </Link>
        </nav>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-12">
        <h1 className="text-3xl font-bold">{title}</h1>
        <p className="mt-2 text-sm text-gray-500">Last updated: {lastUpdated}</p>

        <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <strong>Draft — pending legal review.</strong> This page describes personalCFO&apos;s
          actual data practices as of the date above, but has not been reviewed by counsel. Do
          not treat it as a substitute for legal advice, and expect it to be replaced with
          reviewed copy before public launch.
        </div>

        <div className="mt-10 space-y-8 text-gray-700 leading-relaxed [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-gray-900 [&_h2]:mb-2">
          {children}
        </div>
      </main>

      <footer className="border-t border-gray-200">
        <div className="max-w-3xl mx-auto px-6 py-8 text-xs text-gray-400">
          © {new Date().getFullYear()} personalCFO. All rights reserved.
        </div>
      </footer>
    </div>
  );
}
