"use client";

import { useRef, useState, type FormEvent } from "react";
import { usePathname } from "next/navigation";
import { submitFeedback } from "@/lib/api";
import type { FeedbackCategory } from "@/lib/types";

const CATEGORIES: { value: FeedbackCategory; label: string }[] = [
  { value: "general", label: "General feedback" },
  { value: "bug", label: "Report a bug" },
  { value: "feature", label: "Request a feature" },
];

const MAX_ATTACHMENT_MB = 5;

export default function FeedbackButton() {
  const pathname = usePathname();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<FeedbackCategory>("general");
  const [message, setMessage] = useState("");
  const [attachment, setAttachment] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  function reset() {
    setCategory("general");
    setMessage("");
    setAttachment(null);
    setError(null);
    setSubmitted(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleClose() {
    setOpen(false);
    reset();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    if (file && file.size > MAX_ATTACHMENT_MB * 1024 * 1024) {
      setError(`Attachment must be ${MAX_ATTACHMENT_MB}MB or smaller`);
      e.target.value = "";
      setAttachment(null);
      return;
    }
    setError(null);
    setAttachment(file);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await submitFeedback(category, message, pathname ?? undefined, attachment);
      setMessage("");
      setAttachment(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
      >
        Feedback
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-lg">
            {submitted ? (
              <>
                <h3 className="text-lg font-bold text-gray-900 mb-1">Thanks for the feedback!</h3>
                <p className="text-sm text-gray-500 mb-6">We read every submission.</p>
                <div className="flex justify-end gap-3">
                  <button
                    onClick={reset}
                    className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
                  >
                    Send more feedback
                  </button>
                  <button
                    onClick={handleClose}
                    className="px-4 py-2 text-sm font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Close
                  </button>
                </div>
              </>
            ) : (
              <>
                <h3 className="text-lg font-bold text-gray-900 mb-1">Send feedback</h3>
                <p className="text-sm text-gray-500 mb-4">
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
                      rows={5}
                      maxLength={5000}
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                      placeholder="What's on your mind?"
                      className="w-full px-3 py-2 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Attachment <span className="text-gray-400 font-normal">(optional, image or PDF, max {MAX_ATTACHMENT_MB}MB)</span>
                    </label>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/png,image/jpeg,image/gif,image/webp,application/pdf"
                      onChange={handleFileChange}
                      className="w-full text-sm text-gray-600 file:mr-3 file:py-2 file:px-3 file:rounded-xl file:border-0 file:bg-gray-100 file:text-sm file:font-medium file:text-gray-700 hover:file:bg-gray-200"
                    />
                  </div>
                  {error && <p className="text-sm text-red-600">{error}</p>}
                  <div className="flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={handleClose}
                      disabled={loading}
                      className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={loading || !message.trim()}
                      className="px-4 py-2 rounded-xl font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      {loading ? "Sending…" : "Send feedback"}
                    </button>
                  </div>
                </form>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
