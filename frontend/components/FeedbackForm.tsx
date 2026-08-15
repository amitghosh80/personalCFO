"use client";

import { useState, type FormEvent } from "react";
import { usePathname } from "next/navigation";
import { submitFeedback } from "@/lib/api";
import type { FeedbackCategory } from "@/lib/types";

const CATEGORIES: { value: FeedbackCategory; label: string }[] = [
  { value: "general", label: "General feedback" },
  { value: "bug", label: "Report a bug" },
  { value: "feature", label: "Request a feature" },
];

export default function FeedbackForm() {
  const pathname = usePathname();
  const [category, setCategory] = useState<FeedbackCategory>("general");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await submitFeedback(category, message, pathname ?? undefined);
      setMessage("");
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  if (submitted) {
    return (
      <div className="max-w-lg">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Thanks for the feedback!</h1>
        <p className="text-gray-500 mb-6">We read every submission.</p>
        <button
          onClick={() => setSubmitted(false)}
          className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
        >
          Send more feedback
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Send feedback</h1>
      <p className="text-gray-500 mb-6">
        Found a bug, want a feature, or have general thoughts? Let us know.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as FeedbackCategory)}
            className="w-full px-3 py-2 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Message</label>
          <textarea
            required
            rows={6}
            maxLength={5000}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="What's on your mind?"
            className="w-full px-3 py-2 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={loading || !message.trim()}
          className="w-full py-3 rounded-xl font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Sending…" : "Send feedback"}
        </button>
      </form>
    </div>
  );
}
