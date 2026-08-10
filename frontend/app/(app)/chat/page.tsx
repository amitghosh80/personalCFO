import ChatInterface from "@/components/ChatInterface";
import StepNav from "@/components/StepNav";

export default function ChatPage({ searchParams }: { searchParams: { job?: string; q?: string } }) {
  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-4 py-10">
        <StepNav backHistory className="mb-4" />
        <h1 className="text-xl font-semibold mb-4">Ask your money</h1>
        <ChatInterface jobId={searchParams.job} initialMessage={searchParams.q} />
      </div>
    </main>
  );
}
