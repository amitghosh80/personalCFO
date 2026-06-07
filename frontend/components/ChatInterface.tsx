"use client";

import { useState } from "react";
import { sendChatMessage } from "@/lib/api";
import type { ChatMessage, ChatToolUse } from "@/lib/types";

interface DisplayMessage extends ChatMessage {
  tools?: ChatToolUse[];
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    const question = input.trim();
    if (!question || loading) return;
    setError(null);
    setInput("");

    const history: ChatMessage[] = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);
    try {
      const res = await sendChatMessage(question, history);
      setMessages((prev) => [...prev, { role: "assistant", content: res.answer, tools: res.tools_used }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-[70vh]">
      <div className="flex-1 overflow-y-auto space-y-4 p-2">
        {messages.length === 0 && (
          <p className="text-gray-400 text-sm text-center mt-8">
            Ask about your finances — e.g. &ldquo;How much did I spend on dining last quarter?&rdquo;
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            <div
              className={`inline-block rounded-lg px-3 py-2 max-w-[85%] whitespace-pre-wrap text-sm ${
                m.role === "user" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-800"
              }`}
            >
              {m.content}
            </div>
            {m.tools && m.tools.length > 0 && (
              <div className="text-[11px] text-gray-400 mt-1">
                based on: {m.tools.map((t) => t.name).join(", ")}
              </div>
            )}
          </div>
        ))}
        {loading && <div className="text-gray-400 text-sm">Thinking…</div>}
      </div>

      {error && <div className="text-red-600 text-sm px-2 py-1">{error}</div>}

      <div className="flex gap-2 border-t pt-3">
        <input
          className="flex-1 border rounded-lg px-3 py-2 text-sm"
          placeholder="Ask a question about your money…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          disabled={loading}
        />
        <button
          className="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm disabled:opacity-50"
          onClick={send}
          disabled={loading || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
