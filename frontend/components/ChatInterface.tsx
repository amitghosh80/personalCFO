"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getObservations, getStarterQuestions, sendChatMessage } from "@/lib/api";
import type { ChatMessage, ChatToolUse, DataCoverage, Observation } from "@/lib/types";

function AnswerMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="list-disc pl-5 mb-2 last:mb-0">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-5 mb-2 last:mb-0">{children}</ol>,
        table: ({ children }) => (
          <div className="overflow-x-auto my-2 rounded-lg border border-gray-200">
            <table className="w-full text-sm border-collapse">{children}</table>
          </div>
        ),
        thead: ({ children }) => <thead className="bg-gray-50">{children}</thead>,
        th: ({ children }) => (
          <th className="text-left px-3 py-1.5 font-medium text-gray-500 border-b border-gray-200">
            {children}
          </th>
        ),
        td: ({ children }) => <td className="px-3 py-1.5 border-b border-gray-100">{children}</td>,
        code: ({ children }) => (
          <code className="bg-gray-200/70 rounded px-1 py-0.5 text-xs">{children}</code>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

interface DisplayMessage extends ChatMessage {
  tools?: ChatToolUse[];
}

function coverageText(c: DataCoverage): string | null {
  if (!c.date_range) return null;
  const accounts = `${c.account_count} account${c.account_count === 1 ? "" : "s"}`;
  return `Based on your ${c.date_range.from} – ${c.date_range.to} data from ${accounts}.`;
}

export default function ChatInterface({
  jobId,
  initialMessage,
}: {
  jobId?: string;
  initialMessage?: string;
}) {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [starters, setStarters] = useState<string[]>([]);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [coverage, setCoverage] = useState<DataCoverage | null>(null);

  useEffect(() => {
    getStarterQuestions().then(setStarters).catch(() => {});
    if (jobId) {
      // PRD F4: 2–3 proactive observations appear automatically after an import.
      getObservations(jobId).then(setObservations).catch(() => {});
    }
  }, [jobId]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || loading) return;
    setError(null);
    setInput("");

    const history: ChatMessage[] = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);
    try {
      const res = await sendChatMessage(q, history);
      setMessages((prev) => [...prev, { role: "assistant", content: res.answer, tools: res.tools_used }]);
      if (res.coverage) setCoverage(res.coverage);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  const firedInitial = useRef(false);
  useEffect(() => {
    if (initialMessage && !firedInitial.current) {
      firedInitial.current = true;
      ask(initialMessage);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialMessage]);

  const showStarters = !loading && starters.length > 0;

  return (
    <div className="flex flex-col h-[70vh]">
      <div className="flex-1 overflow-y-auto space-y-4 p-2">
        {/* Proactive post-import briefing */}
        {observations.length > 0 && messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Since your last import</p>
            {observations.map((o, i) => (
              <div key={i} className="rounded-lg border border-gray-200 bg-white px-3 py-2">
                <p className="text-sm font-medium text-gray-800">{o.title}</p>
                <p className="text-xs text-gray-500 mt-0.5">{o.text}</p>
              </div>
            ))}
          </div>
        )}

        {messages.length === 0 && observations.length === 0 && (
          <p className="text-gray-400 text-sm text-center mt-8">
            Ask about your finances — e.g. &ldquo;How much did I spend on dining last quarter?&rdquo;
          </p>
        )}

        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            <div
              className={`inline-block rounded-lg px-3 py-2 max-w-[85%] text-sm ${
                m.role === "user" ? "bg-blue-600 text-white whitespace-pre-wrap" : "bg-gray-100 text-gray-800"
              }`}
            >
              {m.role === "assistant" ? <AnswerMarkdown content={m.content} /> : m.content}
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

      {/* Coverage footer (PRD F4 scope disclosure) */}
      {coverage && coverageText(coverage) && (
        <div className="text-[11px] text-gray-400 px-2 pb-1">{coverageText(coverage)}</div>
      )}

      {/* Starter questions */}
      {showStarters && (
        <div className="flex flex-wrap gap-2 px-2 pb-2">
          {starters.map((q) => (
            <button
              key={q}
              onClick={() => ask(q)}
              className="text-xs px-3 py-1.5 rounded-full border border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {error && <div className="text-red-600 text-sm px-2 py-1">{error}</div>}

      <div className="flex gap-2 border-t pt-3">
        <input
          className="flex-1 border rounded-lg px-3 py-2 text-sm"
          placeholder="Ask a question about your money…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask(input)}
          disabled={loading}
        />
        <button
          className="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm disabled:opacity-50"
          onClick={() => ask(input)}
          disabled={loading || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
