import type { ReactNode } from "react";

/**
 * Shared card shell for the top-level sections of a page (colored title bar +
 * padded body) so distinct areas — e.g. the View import page's Financial
 * Profile, Automated Insights, and monthly breakdown — read as clearly
 * separated containers instead of one continuous scroll of content. Each
 * `accent` maps to a full, literal set of Tailwind classes (not built via
 * string interpolation) so the JIT compiler can see and keep them.
 */
const ACCENTS = {
  blue: {
    card: "border-blue-200",
    header: "bg-blue-50 border-blue-100",
    title: "text-blue-900",
    description: "text-blue-500",
    dot: "bg-blue-500",
  },
  violet: {
    card: "border-violet-200",
    header: "bg-violet-50 border-violet-100",
    title: "text-violet-900",
    description: "text-violet-500",
    dot: "bg-violet-500",
  },
  emerald: {
    card: "border-emerald-200",
    header: "bg-emerald-50 border-emerald-100",
    title: "text-emerald-900",
    description: "text-emerald-600",
    dot: "bg-emerald-500",
  },
} as const;

export type SectionAccent = keyof typeof ACCENTS;

export default function SectionCard({
  title,
  description,
  accent = "blue",
  children,
}: {
  title: string;
  description?: string;
  accent?: SectionAccent;
  children: ReactNode;
}) {
  const a = ACCENTS[accent];
  return (
    <div className={`mb-6 rounded-xl border ${a.card} overflow-hidden bg-white shadow-sm`}>
      <div className={`px-5 py-3 border-b ${a.header} flex items-center gap-2.5`}>
        <span className={`w-2 h-2 rounded-full shrink-0 ${a.dot}`} />
        <div>
          <h3 className={`font-semibold ${a.title}`}>{title}</h3>
          {description && <p className={`text-xs ${a.description} mt-0.5`}>{description}</p>}
        </div>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}
