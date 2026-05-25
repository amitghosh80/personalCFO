import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PersonalCFO",
  description: "Your AI-powered financial advisor",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen">
        <nav className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="max-w-5xl mx-auto flex items-center justify-between">
            <a href="/" className="text-lg font-bold text-gray-900 tracking-tight">
              PersonalCFO
            </a>
            <a
              href="/transactions"
              className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
            >
              All Transactions
            </a>
          </div>
        </nav>
        <main className="max-w-5xl mx-auto px-6 py-10">{children}</main>
      </body>
    </html>
  );
}
