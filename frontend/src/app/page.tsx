import Link from "next/link";

/**
 * Landing page.
 *
 * Deliberately plain (plan §9): the fee is stated on the page rather than
 * revealed at checkout, there are no countdown timers or "limited slots"
 * prompts, and there is no social proof section until there are real
 * placements to name. The audience is students and parents who are already
 * wary of scams in this industry — pressure tactics cost more trust than they
 * buy clicks.
 */

const STEPS = [
  {
    title: "Create your account",
    body: "Tell us where you want to study and what you've completed so far.",
  },
  {
    title: "Get your checklist",
    body: "Every document your chosen school actually asks for, in one list, with the reason it's needed.",
  },
  {
    title: "Upload and track",
    body: "Upload each document once. We review it and tell you plainly if something needs redoing — and why.",
  },
  {
    title: "Apply with everything in order",
    body: "You submit a complete file, and you can see exactly where your application stands.",
  },
];

const INCLUDED = [
  "A document checklist built from your school's real requirements",
  "Document review with written feedback on anything rejected",
  "Application tracking across every school you apply to",
  "A counsellor you can message inside the platform",
];

const NOT_INCLUDED = [
  "Admission is decided by the school, not by us",
  "Visa decisions are made by the embassy",
  "School application fees, test fees and visa fees are paid separately",
];

export default function Home() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16 sm:py-24">
      <header className="space-y-5">
        <p className="text-sm font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">
          Nasuru
        </p>
        <h1 className="text-3xl leading-tight font-semibold text-slate-900 sm:text-4xl dark:text-slate-50">
          We guide Nigerian students through university applications abroad — application tracking,
          document checklists and support in one place.
        </h1>
        <p className="text-lg text-slate-600 dark:text-slate-300">
          Most applications fail on paperwork, not on grades. We tell you exactly what your school
          needs, check each document before you submit, and keep the whole file in one place.
        </p>
        <div className="flex flex-wrap items-center gap-4 pt-2">
          <Link
            href="/signup"
            className="rounded-lg bg-slate-900 px-6 py-3 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
          >
            Create an account
          </Link>
          <Link href="/login" className="text-sm font-medium text-slate-700 underline underline-offset-4 dark:text-slate-300">
            I already have an account
          </Link>
        </div>
      </header>

      <section className="mt-16 space-y-6">
        <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">How it works</h2>
        <ol className="space-y-5">
          {STEPS.map((step, index) => (
            <li key={step.title} className="flex gap-4">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white dark:bg-slate-100 dark:text-slate-900">
                {index + 1}
              </span>
              <div>
                <h3 className="font-medium text-slate-900 dark:text-slate-100">{step.title}</h3>
                <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-400">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {/* The fee is stated here, before signup — hiding it until checkout costs
          trust with exactly the audience least able to afford a surprise. */}
      <section className="mt-16 rounded-xl border border-slate-200 p-6 dark:border-slate-800">
        <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">What it costs</h2>
        <p className="mt-3 text-2xl font-semibold text-slate-900 dark:text-slate-50">
          ₦5,000 <span className="text-base font-normal text-slate-600 dark:text-slate-400">one-time access fee</span>
        </p>

        <div className="mt-6 grid gap-6 sm:grid-cols-2">
          <div>
            <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">What it includes</h3>
            <ul className="mt-2 space-y-1.5 text-sm text-slate-600 dark:text-slate-400">
              {INCLUDED.map((item) => (
                <li key={item} className="flex gap-2">
                  <span aria-hidden className="text-emerald-600 dark:text-emerald-400">✓</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">What it does not include</h3>
            <ul className="mt-2 space-y-1.5 text-sm text-slate-600 dark:text-slate-400">
              {NOT_INCLUDED.map((item) => (
                <li key={item} className="flex gap-2">
                  <span aria-hidden className="text-slate-400">–</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <p className="mt-6 text-sm text-slate-600 dark:text-slate-400">
          Read the{" "}
          <Link href="/refund-policy" className="underline underline-offset-2">
            refund policy
          </Link>{" "}
          and{" "}
          <Link href="/terms" className="underline underline-offset-2">
            terms
          </Link>{" "}
          before you pay.
        </p>
      </section>

      <footer className="mt-16 border-t border-slate-200 pt-8 text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400">
        <nav className="flex flex-wrap gap-x-6 gap-y-2">
          <Link href="/privacy" className="hover:underline">Privacy policy</Link>
          <Link href="/terms" className="hover:underline">Terms of service</Link>
          <Link href="/refund-policy" className="hover:underline">Refund policy</Link>
          <Link href="/contact" className="hover:underline">Contact</Link>
        </nav>
        <p className="mt-4">
          Nasuru.com Limited. Your documents are stored encrypted and processed in line with the
          Nigeria Data Protection Regulation.
        </p>
      </footer>
    </main>
  );
}
