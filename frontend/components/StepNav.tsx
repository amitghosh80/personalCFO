"use client";

import { useRouter } from "next/navigation";

/**
 * Consistent Back/Next navigation bar shared across the app.
 *
 * Either button can be driven by a route (`backHref`/`nextHref`) or a callback
 * (`onBack`/`onNext`); a callback wins if both are given. Omit both and the
 * button is hidden. Back is a ghost/outline button on the left; Next is the
 * primary blue action on the right.
 *
 * Note: the Scan step auto-advances, so callers never point Back at it — doing
 * so would re-run the animation and bounce the user forward again.
 */

interface StepNavProps {
  backHref?: string;
  onBack?: () => void;
  /** Use browser history for Back (for standalone pages with no fixed parent). */
  backHistory?: boolean;
  backLabel?: string;

  nextHref?: string;
  onNext?: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
  nextLoading?: boolean;

  /** Secondary actions rendered just left of Next (e.g. Export, Skip). */
  children?: React.ReactNode;
  className?: string;
}

export default function StepNav({
  backHref,
  onBack,
  backHistory = false,
  backLabel = "Back",
  nextHref,
  onNext,
  nextLabel = "Next",
  nextDisabled = false,
  nextLoading = false,
  children,
  className = "mt-8",
}: StepNavProps) {
  const router = useRouter();

  const hasBack = Boolean(onBack || backHref || backHistory);
  const hasNext = Boolean(onNext || nextHref);
  const hasRight = hasNext || Boolean(children);

  const handleBack = () => {
    if (onBack) return onBack();
    if (backHref) return router.push(backHref);
    if (backHistory) router.back();
  };

  const handleNext = () => {
    if (onNext) return onNext();
    if (nextHref) router.push(nextHref);
  };

  if (!hasBack && !hasRight) return null;

  return (
    <div className={`flex items-center justify-between gap-3 flex-wrap ${className}`}>
      {hasBack ? (
        <button
          type="button"
          onClick={handleBack}
          className="inline-flex items-center gap-1.5 px-5 py-3 text-gray-700 border border-gray-300 rounded-xl hover:bg-gray-50 transition-colors"
        >
          <span aria-hidden>←</span>
          {backLabel}
        </button>
      ) : (
        <span />
      )}

      {hasRight && (
        <div className="flex items-center gap-3 flex-wrap">
          {children}
          {hasNext && (
            <button
              type="button"
              onClick={handleNext}
              disabled={nextDisabled || nextLoading}
              className="inline-flex items-center gap-1.5 px-6 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 disabled:opacity-40 transition-colors"
            >
              {nextLoading ? "Saving…" : nextLabel}
              {!nextLoading && <span aria-hidden>→</span>}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
