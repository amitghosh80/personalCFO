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
    dimension: "Memory",
    chatgpt: "Each conversation starts from zero; statements get re-pasted next month.",
    cfo: "Every import adds to one permanent, structured ledger that gets smarter over time.",
  },
  {
    dimension: "Accuracy",
    chatgpt: "Reads numbers off a PDF and reasons in prose; estimates and rounding aren't traceable.",
    cfo: "Every dollar in every answer comes from a tool call against the real transaction database — never generated, never estimated.",
  },
  {
    dimension: "Parsing",
    chatgpt: "One format, one institution, one shot; mixed PDF layouts and sign conventions trip up a general model.",
    cfo: "Purpose-built parsers per institution, with automatic sign-convention detection and duplicate removal across files.",
  },
  {
    dimension: "Proactivity",
    chatgpt: "Only answers what you think to ask.",
    cfo: "A 10-signal Insight Feed flags cashflow risk, subscription creep, duplicate charges, and spending spikes automatically.",
  },
  {
    dimension: "Income intelligence",
    chatgpt: "Treats every deposit the same.",
    cfo: "Classifies salary, freelance, rental, interest, and gig income, and asks you to confirm what it's unsure about.",
  },
  {
    dimension: "Privacy",
    chatgpt: "Statements become part of a general-purpose chat history.",
    cfo: "Purpose-built for financial data: encrypted at rest, account numbers masked, never used to train a model, never sold.",
  },
  {
    dimension: "Auditability",
    chatgpt: "A paragraph of prose with no way to check its work.",
    cfo: "Every insight links back to the specific transactions behind it, with a confidence score attached.",
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

          {/* Hero visual: one traceable mock chat exchange (spec §5.2). */}
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
              You can — and you&apos;ll get an answer. The question is whether you can trust it, and
              whether it&apos;s still there next month.
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
            ChatGPT is a brilliant generalist. personalCFO is the one place that already knows your
            transactions — and only ever tells you what they actually say.
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
