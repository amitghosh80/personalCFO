import ChatInterface from "@/components/ChatInterface";

export default function ChatPage({ searchParams }: { searchParams: { job?: string; q?: string } }) {
  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto px-4 py-8">
        <ChatInterface jobId={searchParams.job} initialMessage={searchParams.q} />
      </div>
    </main>
  );
}
