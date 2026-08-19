"use client";

import { useEffect, useRef, type Dispatch, type SetStateAction } from "react";
import Script from "next/script";
import { useRouter } from "next/navigation";
import { signInWithGoogle } from "@/lib/api";
import { setToken } from "@/lib/auth";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
          }) => void;
          renderButton: (parent: HTMLElement, options: Record<string, unknown>) => void;
        };
      };
    };
  }
}

const CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

export default function GoogleSignInButton({
  setError,
}: {
  setError: Dispatch<SetStateAction<string | null>>;
}) {
  const router = useRouter();
  const buttonRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!CLIENT_ID) return;

    let cancelled = false;

    async function handleCredential(response: { credential: string }) {
      setError(null);
      try {
        const res = await signInWithGoogle(response.credential);
        setToken(res.access_token);
        router.push("/app");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Google sign-in failed");
      }
    }

    function render() {
      if (cancelled || !window.google || !buttonRef.current) return;
      window.google.accounts.id.initialize({ client_id: CLIENT_ID!, callback: handleCredential });
      window.google.accounts.id.renderButton(buttonRef.current, {
        theme: "outline",
        size: "large",
        width: 320,
      });
    }

    if (window.google) {
      render();
    } else {
      const interval = setInterval(() => {
        if (window.google) {
          clearInterval(interval);
          render();
        }
      }, 100);
      return () => {
        cancelled = true;
        clearInterval(interval);
      };
    }
    return () => {
      cancelled = true;
    };
  }, [router, setError]);

  if (!CLIENT_ID) return null;

  return (
    <div className="mb-6">
      <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" />
      <div ref={buttonRef} className="flex justify-center" />
      <div className="flex items-center gap-3 mt-6">
        <div className="h-px flex-1 bg-gray-200" />
        <span className="text-xs text-gray-400">or</span>
        <div className="h-px flex-1 bg-gray-200" />
      </div>
    </div>
  );
}
