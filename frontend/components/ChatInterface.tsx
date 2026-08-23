"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import ChatToolChart from "@/components/ChatToolChart";
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
        strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
        table: ({ children }) => (
          <div className="overflow-x-auto my-2 rounded-lg border border-gray-200 shadow-sm">
            <table className="w-full text-sm border-collapse">{children}</table>
          </div>
        ),
        thead: ({ children }) => (
          <thead className="bg-gradient-to-b from-blue-50 to-blue-50/60 sticky top-0">{children}</thead>
        ),
        th: ({ children }) => (
          <th className="text-left px-3 py-2 font-semibold text-blue-900 border-b border-blue-100 whitespace-nowrap">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="px-3 py-1.5 border-b border-gray-100 [font-variant-numeric:tabular-nums] whitespace-nowrap">
            {children}
          </td>
        ),
        tr: ({ children }) => <tr className="odd:bg-white even:bg-gray-50/60 hover:bg-blue-50/50 transition-colors">{children}</tr>,
        code: ({ children }) => (
          <code className="bg-gray-200/70 rounded px-1 py-0.5 text-xs">{children}</code>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

const TOOL_STYLES: Record<string, { emoji: string; className: string }> = {
  spending_by_category: { emoji: "💳", className: "bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-200" },
  cashflow_summary: { emoji: "🔀", className: "bg-violet-50 text-violet-700 ring-1 ring-inset ring-violet-200" },
  income_summary: { emoji: "💰", className: "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200" },
  compare_periods: { emoji: "📊", className: "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200" },
  recurring_charges: { emoji: "🔁", className: "bg-orange-50 text-orange-700 ring-1 ring-inset ring-orange-200" },
  search_transactions: { emoji: "🔎", className: "bg-gray-100 text-gray-600 ring-1 ring-inset ring-gray-200" },
};

function toolStyle(name: string) {
  return TOOL_STYLES[name] ?? { emoji: "⚙", className: "bg-gray-100 text-gray-600 ring-1 ring-inset ring-gray-200" };
}

interface DisplayMessage extends ChatMessage {
  tools?: ChatToolUse[];
}

function coverageText(c: DataCoverage): string | null {
  if (!c.date_range) return null;
  const accounts = `${c.account_count} account${c.account_count === 1 ? "" : "s"}`;
  return `Based on your ${c.date_range.from} – ${c.date_range.to} data from ${accounts}.`;
}

function AssistantAvatar() {
  return (
    <div className="h-8 w-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white flex items-center justify-center text-xs font-bold shrink-0 shadow-sm">
      $
    </div>
  );
}

function UserAvatar() {
  return (
    <div className="h-8 w-8 rounded-full bg-gradient-to-br from-gray-200 to-gray-300 text-gray-700 flex items-center justify-center text-xs font-semibold shrink-0 shadow-sm">
      Y
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-end gap-2 animate-fade-in-up">
      <AssistantAvatar />
      <div className="inline-flex items-center gap-1 rounded-2xl rounded-bl-sm bg-gray-100 px-4 py-3">
        <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.3s]" />
        <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.15s]" />
        <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce" />
      </div>
    </div>
  );
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
      <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
    </svg>
  );
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
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getStarterQuestions().then(setStarters).catch(() => {});
    if (jobId) {
      // PRD F4: 2–3 proactive observations appear automatically after an import.
      getObservations(jobId).then(setObservations).catch(() => {});
    }
  }, [jobId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

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
    <div className="flex flex-col h-[85vh] rounded-3xl border border-gray-200 bg-white shadow-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-3.5 bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-700 text-white shrink-0">
        <div className="h-9 w-9 rounded-full bg-white/15 backdrop-blur flex items-center justify-center text-base font-bold ring-1 ring-white/30">
          $
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold leading-tight">AskCFO</p>
          <p className="text-[11px] text-blue-100/90 leading-tight truncate">
            Your personal finance analyst
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 p-4 bg-gradient-to-b from-gray-50/60 to-white">
        {/* Proactive post-import briefing */}
        {observations.length > 0 && messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Since your last import</p>
            {observations.map((o, i) => (
              <div
                key={i}
                className="rounded-lg border border-gray-200 border-l-4 border-l-blue-500 bg-white px-3 py-2 shadow-sm animate-fade-in-up"
              >
                <p className="text-sm font-medium text-gray-800">{o.title}</p>
                <p className="text-xs text-gray-500 mt-0.5">{o.text}</p>
              </div>
            ))}
          </div>
        )}

        {messages.length === 0 && observations.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="h-14 w-14 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white flex items-center justify-center text-2xl font-bold mb-3 shadow-md">
              $
            </div>
            <p className="text-gray-600 text-sm font-medium">
              Ask about your finances
            </p>
            <p className="text-gray-400 text-sm mt-1 max-w-sm">
              e.g. &ldquo;How much did I spend on dining last quarter?&rdquo;
            </p>
            <p className="text-gray-400 text-xs mt-3 max-w-sm">
              Answers are generated from your imported data and are not financial, tax, or legal advice.
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex items-start gap-2 animate-fade-in-up ${m.role === "user" ? "flex-row-reverse" : ""}`}
          >
            {m.role === "user" ? <UserAvatar /> : <AssistantAvatar />}
            <div className={`max-w-[88%] sm:max-w-[80%] ${m.role === "user" ? "text-right" : "text-left"}`}>
              <div
                className={`inline-block rounded-2xl px-4 py-2.5 text-sm shadow-sm ${
                  m.role === "user"
                    ? "rounded-br-sm bg-gradient-to-br from-blue-600 to-indigo-600 text-white whitespace-pre-wrap"
                    : "rounded-bl-sm bg-gray-100 text-gray-800"
                }`}
              >
                {m.role === "assistant" ? <AnswerMarkdown content={m.content} /> : m.content}
              </div>
              {m.tools && m.tools.length > 0 && (
                <>
                  <div className="mt-1.5 flex flex-wrap gap-1 justify-start">
                    {m.tools.map((t, ti) => {
                      const style = toolStyle(t.name);
                      return (
                        <span
                          key={`${t.name}-${ti}`}
                          className={`inline-flex items-center gap-1 rounded-full text-[10px] px-2 py-0.5 font-medium ${style.className}`}
                        >
                          <span aria-hidden>{style.emoji}</span>
                          {t.name.replace(/_/g, " ")}
                        </span>
                      );
                    })}
                  </div>
                  <div className="text-left">
                    {m.tools.map((t, ti) => (
                      <ChatToolChart key={`${t.name}-chart-${ti}`} tool={t} />
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        ))}
        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Coverage footer (PRD F4 scope disclosure) */}
      {coverage && coverageText(coverage) && (
        <div className="text-[11px] text-gray-400 px-4 pb-1 pt-2 border-t border-gray-100">{coverageText(coverage)}</div>
      )}

      {/* Starter questions */}
      {showStarters && (
        <div className="flex flex-wrap gap-2 px-4 pb-3 pt-2">
          {starters.map((q) => (
            <button
              key={q}
              onClick={() => ask(q)}
              className="text-xs px-3 py-1.5 rounded-full border border-gray-200 bg-white text-gray-600 shadow-sm hover:border-blue-300 hover:text-blue-700 hover:shadow transition-all"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {error && <div className="text-red-600 text-sm px-4 py-1">{error}</div>}

      <div className="flex items-center gap-2 border-t border-gray-100 px-4 py-3.5 bg-white shrink-0">
        <input
          className="flex-1 border border-gray-200 rounded-full px-4 py-2.5 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-shadow"
          placeholder="Ask a question about your money…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask(input)}
          disabled={loading}
        />
        <button
          className="h-10 w-10 shrink-0 flex items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-indigo-600 text-white hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm"
          onClick={() => ask(input)}
          disabled={loading || !input.trim()}
          aria-label="Send"
        >
          <SendIcon />
        </button>
      </div>
    </div>
  );
}
