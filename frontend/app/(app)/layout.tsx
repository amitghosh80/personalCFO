export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <nav className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <a href="/app" className="text-lg font-bold text-gray-900 tracking-tight">
            PersonalCFO
          </a>
          <div className="flex items-center gap-5">
            <a href="/app" className="text-sm text-blue-600 hover:text-blue-800 transition-colors">
              Import
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
          </div>
        </div>
      </nav>
      <main className="max-w-5xl mx-auto px-6 py-10">{children}</main>
    </>
  );
}
