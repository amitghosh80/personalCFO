"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { forgotPassword } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await forgotPassword(email);
      setMessage(res.message);
    } catch {
      // Show the same generic message on error too, so failures never reveal
      // whether an account exists for this email.
      setMessage("If that email is registered, we've sent a password reset link.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Reset your password</h1>
        <p className="text-gray-500 mb-6">
          Enter your email and we&apos;ll send you a link to reset your password.
        </p>
        {message ? (
          <p className="text-sm text-gray-700">{message}</p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-xl font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Please wait…" : "Send reset link"}
            </button>
          </form>
        )}
        <p className="text-sm text-gray-500 mt-6 text-center">
          <Link href="/login" className="text-blue-600 hover:text-blue-800">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
