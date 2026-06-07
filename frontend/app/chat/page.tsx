import ChatInterface from "@/components/ChatInterface";

export default function ChatPage() {
  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-4 py-10">
        <h1 className="text-xl font-semibold mb-4">Ask your money</h1>
        <ChatInterface />
      </div>
    </main>
  );
}
