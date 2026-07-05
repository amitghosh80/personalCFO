import Link from "next/link";

/**
 * Marketing landing page (PRD F6). Server component — no client JS needed:
 * the nav is sticky via CSS and section links are plain hash anchors.
 *
 * Copy is lifted from specs/personalCFO_Landing_Page_Spec.docx. Tone guardrails
 * (spec §6/§7): flat and clean, one accent color (blue-600) reserved for CTAs
 * and the personalCFO side of the comparison, concrete numbers over adjectives,
 * product mockups instead of stock imagery, no gamification.
 */

const COMPARISON: { dimension: string; chatgpt: string; cfo: string }[] = [
  {
    dimension: "Who does the math",
    chatgpt: "Computes totals by reasoning over rows in the prompt — it can miscategorize a row, get a credit-card sign backwards, and confidently return the wrong total.",
    cfo: "Never does the arithmetic. The chatbot calls structured tools that query the database; the model only reads back the result.",
  },
  {
    dimension: "Data volume",
    chatgpt: "3 accounts × 12 months is 3,000–5,000+ transactions — past the point a context window holds, so you re-upload every session and overlapping dates get double-counted.",
    cfo: "Builds one persistent, deduplicated ledger that grows with each import — nothing to re-paste, no double-counting.",
  },
  {
    dimension: "Statement parsing",
    chatgpt: "Every bank uses different sign conventions, layouts, and encodings. A general model parses them inconsistently and fails silently.",
    cfo: "Institution-specific parsers with automatic sign-inversion detection and duplicate removal across files.",
  },
  {
    dimension: "Income intelligence",
    chatgpt: "Treats every deposit the same, and you'd re-explain what's salary vs. transfer vs. refund every month.",
    cfo: "A classification layer separates salary, freelance, rental, interest, and gig income, asks you to confirm the unsure ones, and persists the decision.",
  },
  {
    dimension: "Proactivity",
    chatgpt: "A chat session can only answer what you ask — it can't surface what you didn't think to ask about.",
    cfo: "Flags new subscriptions, duplicate charges, and cashflow risk on its own, because it remembers across months.",
  },
  {
    dimension: "Privacy",
    chatgpt: "Statements become part of a general-purpose chat history.",
    cfo: "Purpose-built for financial data: encrypted at rest, account numbers masked, never used to train a model, never sold.",
  },
  {
    dimension: "Auditability",
    chatgpt: "A fluent paragraph with no way to check its work.",
    cfo: "Every figure links back to the exact transactions behind it, with a confidence score attached.",
  },
];

const STEPS: { title: string; body: string }[] = [
  {
    title: "Upload statements",
    body: "Drag in PDFs or CSVs from any of your accounts (Chase, Amex, Bank of America, Citi, Capital One, Wells Fargo, and more). Multiple files, multiple institutions, one import.",
  },
  {
    title: "Watch it scan",
    body: "A live scan shows the system finding income, large expenses, and transfers in real time. Not a spinner: a window into the reasoning.",
  },
  {
    title: "Confirm your income",
    body: "A quick, pre-filled review of salary, freelance, rental, and gig income. Usually under three minutes. Accept what's right, correct what's not.",
  },
  {
    title: "Ask anything",
    body: "Chat with your real financial history, and watch the Insight Feed surface what's worth knowing without being asked.",
  },
];

const FEATURES: { title: string; body: string }[] = [
  {
    title: "Multi-institution import",
    body: "Chase, Amex, Bank of America, Citi, Capital One, Wells Fargo, and more, in PDF or CSV, in one batch.",
  },
  {
    title: "Smart income classification",
    body: "Salary, freelance, rental, interest, gig: auto-detected, and easy to correct in under three minutes.",
  },
  {
    title: "Grounded, hallucination-free chat",
    body: "Every figure traces back to a real transaction. If the data doesn't exist to answer a question, the system says so.",
  },
  {
    title: "Proactive Insight Feed",
    body: "Ten detectors surface what's worth knowing before you think to ask.",
  },
  {
    title: "No bank credentials, ever",
    body: "You upload statements you already have. Nothing is linked, nothing is stored beyond what's needed.",
  },
  {
    title: "Built for multi-income earners",
    body: "Most finance apps assume one paycheck. personalCFO doesn't.",
  },
];

// Severity/confidence labels mirror the live detectors in insight_engine.py;
// numbers are illustrative-but-specific per spec §6.
const INSIGHTS: { kind: string; confidence: "high" | "medium"; text: string }[] = [
  {
    kind: "Subscription creep",
    confidence: "medium",
    text: "You've added 3 new subscriptions this quarter — $47/month more than January.",
  },
  {
    kind: "Duplicate charge",
    confidence: "high",
    text: "$89.99 to Adobe appears on two statements, three days apart. Likely a duplicate.",
  },
  {
    kind: "Cashflow risk",
    confidence: "medium",
    text: "At your current pace, you're on track to run about $340 short before your next paycheck.",
  },
];

const CONFIDENCE_STYLES: Record<string, string> = {
  high: "bg-green-100 text-green-800",
  medium: "bg-amber-100 text-amber-800",
};

// Hero ledger mockup: one card showing parsing + expense categorization +
// income classification at a glance. Labels/colors mirror the in-app taxonomy
// (TransactionTable / IncomeReview); numbers are specific per spec §6.
const LEDGER: { date: string; merchant: string; amount: string; credit?: boolean; cat: string; cls: string }[] = [
  { date: "Jun 1", merchant: "Gusto Payroll", amount: "+$6,250.00", credit: true, cat: "Salary", cls: "bg-green-100 text-green-800" },
  { date: "Jun 3", merchant: "Whole Foods Market", amount: "−$142.30", cat: "Food & Drink", cls: "bg-orange-50 text-orange-700" },
  { date: "Jun 5", merchant: "Chevron", amount: "−$61.20", cat: "Transportation", cls: "bg-slate-100 text-slate-600" },
  { date: "Jun 6", merchant: "Stripe Transfer", amount: "+$1,800.00", credit: true, cat: "Freelance", cls: "bg-teal-100 text-teal-800" },
  { date: "Jun 7", merchant: "Netflix", amount: "−$15.49", cat: "Subscriptions", cls: "bg-violet-100 text-violet-700" },
];

function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-bold tracking-tight ${className}`}>
      personal<span className="text-blue-600">CFO</span>
    </span>
  );
}

export default function Landing() {
  return (
    <div className="text-gray-900">
      {/* 5.1 Navigation */}
      <header className="sticky top-0 z-50 bg-white/90 backdrop-blur border-b border-gray-200">
        <nav className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <a href="#top" className="text-lg">
            <Wordmark />
          </a>
          <div className="flex items-center gap-6">
            <a href="#features" className="hidden sm:inline text-sm text-gray-600 hover:text-gray-900 transition-colors">
              Features
            </a>
            <a href="#how-it-works" className="hidden sm:inline text-sm text-gray-600 hover:text-gray-900 transition-colors">
              How it works
            </a>
            <a href="#security" className="hidden sm:inline text-sm text-gray-600 hover:text-gray-900 transition-colors">
              Security
            </a>
            <Link
              href="/app"
              className="text-sm font-semibold px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
            >
              Upload a statement
            </Link>
          </div>
        </nav>
      </header>

      {/* 5.2 Hero */}
      <section id="top" className="bg-white">
        <div className="max-w-6xl mx-auto px-6 py-20 md:py-28 grid md:grid-cols-2 gap-12 items-center">
          <div>
            <h1 className="text-4xl md:text-5xl font-bold leading-tight tracking-tight">
              The financial analyst who never makes up a number.
            </h1>
            <p className="mt-6 text-lg text-gray-600 leading-relaxed">
              Upload your statements and get a structured ledger of your real finances — plus a
              chatbot that only ever says what your data actually shows.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                href="/app"
                className="px-6 py-3 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-700 transition-colors"
              >
                Upload your first statement
              </Link>
              <a
                href="#how-it-works"
                className="px-6 py-3 rounded-xl border border-gray-300 text-gray-700 font-medium hover:bg-gray-50 transition-colors"
              >
                See how it works
              </a>
            </div>
            <p className="mt-4 text-sm text-gray-400">No bank credentials required · Encrypted at rest.</p>
          </div>

          {/* Hero visuals: product mockups showing what the system produces —
              a categorized ledger (parsing + expense/income classification) and
              a traceable chat answer (spec §5.2). */}
          <div className="space-y-4">
            {/* Categorized ledger preview */}
            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium uppercase tracking-wide text-gray-400">
                  Your categorized ledger
                </span>
                <span className="text-[11px] text-gray-400">2 accounts · auto-categorized</span>
              </div>
              <div className="divide-y divide-gray-100">
                {LEDGER.map((r) => (
                  <div key={r.merchant} className="flex items-center gap-3 py-2">
                    <span className="text-xs text-gray-400 w-12 shrink-0">{r.date}</span>
                    <span className="text-sm text-gray-700 truncate flex-1">{r.merchant}</span>
                    <span
                      className={`text-sm font-medium tabular-nums shrink-0 ${r.credit ? "text-green-700" : "text-gray-700"}`}
                    >
                      {r.amount}
                    </span>
                    <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium shrink-0 ${r.cls}`}>
                      {r.cat}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Ask CFO chat */}
            <div className="rounded-2xl border border-gray-200 bg-gray-50 p-5 shadow-sm">
              <div className="text-xs font-medium uppercase tracking-wide text-gray-400 mb-3">
                Ask your money
              </div>
              <div className="space-y-3">
                <div className="text-right">
                  <div className="inline-block rounded-2xl rounded-br-sm bg-blue-600 text-white px-4 py-2 text-sm max-w-[85%]">
                    How much did I spend on dining last month?
                  </div>
                </div>
                <div className="text-left">
                  <div className="inline-block rounded-2xl rounded-bl-sm bg-white border border-gray-200 text-gray-800 px-4 py-2 text-sm max-w-[90%]">
                    <span className="font-semibold">$1,240</span> — up 38% from your 3-month average of
                    $897, driven by 5 charges over $100.
                  </div>
                  <div className="text-[11px] text-gray-400 mt-1">based on: spending_by_category</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 5.3 Problem statement */}
      <section className="bg-gray-50 border-y border-gray-200">
        <div className="max-w-3xl mx-auto px-6 py-20 text-center">
          <h2 className="text-3xl font-bold tracking-tight">You have the data. You don&apos;t have the picture.</h2>
          <p className="mt-6 text-lg text-gray-600 leading-relaxed">
            Most financially active people have four to six accounts across different institutions,
            producing dozens of statements a year that nobody actually reads. Existing finance apps
            force a choice: hand bank credentials to an aggregator and hope the connection holds, or do
            it yourself in a spreadsheet. Neither gets you an answer the moment you actually have a
            question.
          </p>
        </div>
      </section>

      {/* 5.4 Why not just use ChatGPT */}
      <section className="bg-white">
        <div className="max-w-5xl mx-auto px-6 py-20">
          <div className="max-w-3xl">
            <h2 className="text-3xl font-bold tracking-tight">
              Why not just paste your statements into ChatGPT?
            </h2>
            <p className="mt-4 text-lg text-gray-600">
              You can — ChatGPT and Claude will parse a statement and answer. The difference
              isn&apos;t capability, it&apos;s <span className="font-semibold text-gray-900">who does
              the math</span>: they compute totals by reasoning over rows in the prompt, while
              personalCFO runs the numbers in code and has the model read the result. For money,
              &ldquo;fluent but occasionally wrong&rdquo; is worse than a number you can trust.
            </p>
          </div>

          <div className="mt-10 space-y-3">
            {/* Column headers (desktop) */}
            <div className="hidden md:grid grid-cols-[10rem_1fr_1fr] gap-4 px-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
              <div />
              <div>ChatGPT</div>
              <div className="text-blue-700">personalCFO</div>
            </div>
            {COMPARISON.map((row) => (
              <div
                key={row.dimension}
                className="grid md:grid-cols-[10rem_1fr_1fr] gap-3 md:gap-4 md:items-stretch"
              >
                <div className="font-semibold text-gray-800 md:py-4">{row.dimension}</div>
                <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
                  <span className="md:hidden block text-[11px] font-semibold uppercase tracking-wide text-gray-400 mb-1">
                    ChatGPT
                  </span>
                  {row.chatgpt}
                </div>
                <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-gray-800">
                  <span className="md:hidden block text-[11px] font-semibold uppercase tracking-wide text-blue-700 mb-1">
                    personalCFO
                  </span>
                  {row.cfo}
                </div>
              </div>
            ))}
          </div>

          <blockquote className="mt-12 border-l-4 border-blue-600 pl-6 text-xl md:text-2xl font-medium text-gray-800 leading-snug">
            ChatGPT does the math itself and sometimes gets it wrong. personalCFO does the math in
            code and has the LLM read the answer.
          </blockquote>
        </div>
      </section>

      {/* 5.5 How it works */}
      <section id="how-it-works" className="bg-gray-50 border-y border-gray-200">
        <div className="max-w-5xl mx-auto px-6 py-20">
          <h2 className="text-3xl font-bold tracking-tight text-center">
            From statement to answer in four steps.
          </h2>
          <ol className="mt-12 grid gap-8 md:grid-cols-4">
            {STEPS.map((step, i) => (
              <li key={step.title} className="relative">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-600 text-white font-bold">
                  {i + 1}
                </div>
                <h3 className="mt-4 font-semibold text-gray-900">{step.title}</h3>
                <p className="mt-2 text-sm text-gray-600 leading-relaxed">{step.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* 5.6 Feature showcase */}
      <section id="features" className="bg-white">
        <div className="max-w-5xl mx-auto px-6 py-20">
          <h2 className="text-3xl font-bold tracking-tight text-center">What personalCFO does</h2>
          <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="rounded-xl border border-gray-200 bg-white p-6">
                <h3 className="font-semibold text-gray-900">{f.title}</h3>
                <p className="mt-2 text-sm text-gray-600 leading-relaxed">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 5.7 Insight Feed showcase */}
      <section className="bg-gray-50 border-y border-gray-200">
        <div className="max-w-5xl mx-auto px-6 py-20">
          <div className="max-w-2xl">
            <h2 className="text-3xl font-bold tracking-tight">Always watching, never nagging.</h2>
            <p className="mt-4 text-lg text-gray-600">
              An analyst&apos;s flag when something deserves your attention — never a lecture about how
              you spend.
            </p>
          </div>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {INSIGHTS.map((ins) => (
              <div key={ins.kind} className="rounded-xl border border-gray-200 bg-white p-5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-gray-900">{ins.kind}</span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium ${CONFIDENCE_STYLES[ins.confidence]}`}
                  >
                    {ins.confidence} confidence
                  </span>
                </div>
                <p className="mt-3 text-sm text-gray-600 leading-relaxed">{ins.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 5.8 Security & privacy */}
      <section id="security" className="bg-white">
        <div className="max-w-3xl mx-auto px-6 py-20">
          <h2 className="text-3xl font-bold tracking-tight text-center">
            Built like it knows it&apos;s handling your money.
          </h2>
          <ul className="mt-10 space-y-4">
            {[
              "No bank credentials requested, ever.",
              "Transaction data encrypted at rest.",
              "Account numbers masked to the last 4 digits.",
              "No ads, no data selling, no hidden commissions.",
            ].map((claim) => (
              <li key={claim} className="flex items-start gap-3">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-700 text-xs font-bold">
                  ✓
                </span>
                <span className="text-gray-700">{claim}</span>
              </li>
            ))}
          </ul>

          {/* Transparency on AI processing — honest about what leaves the device,
              per spec §5.8 (don't promise more than the system provides). */}
          <div className="mt-8 rounded-xl border border-gray-200 bg-gray-50 p-5">
            <h3 className="text-sm font-semibold text-gray-900">How AI features handle your data</h3>
            <p className="mt-2 text-sm text-gray-600 leading-relaxed">
              Categorization and chat send the minimum necessary data to our model provider, under terms
              that prohibit training on it — never your bank login, never your full account numbers. Your
              statements stay in your own encrypted ledger; nothing is sold or used to build a profile.
            </p>
          </div>
        </div>
      </section>

      {/* 5.9 Final CTA */}
      <section className="bg-gray-900">
        <div className="max-w-3xl mx-auto px-6 py-20 text-center">
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-white">
            Find out what your statements have been saying all along.
          </h2>
          <div className="mt-8">
            <Link
              href="/app"
              className="inline-block px-8 py-4 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-500 transition-colors"
            >
              Upload your first statement — free
            </Link>
          </div>
          <p className="mt-4 text-sm text-gray-400">No bank login required. Takes about 3 minutes.</p>
        </div>
      </section>

      {/* 5.10 Footer */}
      <footer className="bg-white border-t border-gray-200">
        <div className="max-w-6xl mx-auto px-6 py-12 flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <Wordmark className="text-base" />
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-gray-500">
            <a href="#features" className="hover:text-gray-900 transition-colors">Features</a>
            <a href="#how-it-works" className="hover:text-gray-900 transition-colors">How it works</a>
            <a href="#security" className="hover:text-gray-900 transition-colors">Security</a>
            <a href="/privacy" className="hover:text-gray-900 transition-colors">Privacy</a>
            <a href="/terms" className="hover:text-gray-900 transition-colors">Terms</a>
            <a href="mailto:hello@personalcfo.app" className="hover:text-gray-900 transition-colors">Contact</a>
          </div>
        </div>
        <div className="max-w-6xl mx-auto px-6 pb-8 text-xs text-gray-400">
          © {new Date().getFullYear()} personalCFO. All rights reserved.
        </div>
      </footer>
    </div>
  );
}
