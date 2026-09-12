import Link from "next/link";
import { StudentJourney } from "@/components/StudentJourney";
import { ACCESS_FEE, COMPANY, CONTACT, REFUND, formattedAddress } from "@/lib/company";

/**
 * Landing page.
 *
 * The stance from the first version is unchanged and deliberate (plan §9): the
 * fee is on the page rather than revealed at checkout, there are no countdown
 * timers or "limited slots" prompts, and no social proof is claimed until there
 * are real placements to name. The audience is students and parents already
 * wary of scams — pressure tactics cost more trust than they buy clicks.
 *
 * What changed is that looking under-built was costing trust too. A page that
 * reads as unfinished is its own kind of warning sign to this audience, so the
 * argument is now carried by the product itself: the checklist a student
 * actually gets is shown on the page, with a real rejection reason in it.
 *
 * Anything that would be a claim we cannot evidence is a [BRACKETED]
 * placeholder rather than a number someone invented.
 */

const CHECKLIST_CATEGORIES = [
  {
    name: "Documents & transcripts",
    detail:
      "Passport bio-data page, WAEC/NECO, a university transcript covering every completed semester, CV, certified translations.",
  },
  {
    name: "English proof",
    detail:
      "IELTS 6.0–6.5 overall is the usual target. Policies differ by school — we confirm yours in writing before you book a test.",
  },
  {
    name: "German language",
    detail:
      "A2 is the admission minimum. B1 before you travel is what makes the first year survivable.",
  },
  {
    name: "Application forms",
    detail:
      "uni-assist account and entries — every prior institution, each with its own transcript. Motivation letter. Submitted early in the window, not at the deadline.",
  },
  {
    name: "Financial",
    detail:
      "A blocked account covering one year of living costs. The step that most often decides whether the visa happens.",
  },
  {
    name: "Visa & relocation",
    detail: "Admission letter, health insurance, a registered address, the appointment booked.",
  },
  {
    name: "Spouse & family",
    detail:
      "Marriage certificate with a certified translation, and your spouse's own document set. A parallel application with its own timeline.",
  },
];

const NOT_INCLUDED = [
  {
    claim: "“Guaranteed admission.”",
    truth:
      "The university decides. A complete, verified file is the only honest advantage anyone can give you.",
  },
  {
    claim: "“Guaranteed visa.”",
    truth:
      "The embassy decides. No agency influences that, and any that says otherwise is selling you something else.",
  },
  {
    claim: "“Limited slots — pay today.”",
    truth:
      "There is no countdown on this page. The real deadlines are the university’s, and we show you those.",
  },
];

export default function Home() {
  return (
    <div className="bg-canvas">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div className="flex items-center gap-2.5">
            <span
              aria-hidden="true"
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--on-accent)" }}>
                <path d="M20 6 9 17l-5-5" />
              </svg>
            </span>
            <span className="font-display text-xl font-extrabold tracking-tight text-ink">Nasuru</span>
          </div>
          <nav aria-label="Main" className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
            <a href="#journey" className="text-muted hover:text-ink">How it works</a>
            <a href="#checklist" className="text-muted hover:text-ink">What you’ll need</a>
            <a href="#fees" className="text-muted hover:text-ink">Fees</a>
            <Link href="/login" className="font-medium text-ink hover:underline">Sign in</Link>
            <Link
              href="/signup"
              className="rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-on-accent transition hover:bg-accent-hover"
            >
              Create an account
            </Link>
          </nav>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="mx-auto max-w-6xl px-6 py-16 text-center sm:py-20">
          <p className="text-xs font-bold tracking-[0.14em] text-accent uppercase">
            For Nigerians applying to German universities
          </p>
          <h1 className="font-display mx-auto mt-4 max-w-4xl text-4xl leading-[1.08] font-extrabold tracking-tight text-balance text-ink sm:text-5xl">
            Stop tracking your application in a WhatsApp chat and a notes app
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg leading-relaxed text-muted">
            One checklist, built from your university’s real requirements. Upload a document once and it counts
            everywhere it’s needed. See what’s verified, what’s waiting on us, and what’s waiting on you.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/signup"
              className="rounded-lg bg-accent px-7 py-3.5 text-base font-bold text-on-accent transition hover:bg-accent-hover"
            >
              See your checklist — {ACCESS_FEE.formatted} once
            </Link>
            <span className="text-sm text-subtle">
              Refundable for {REFUND.coolingOffDays} days. No subscription.
            </span>
          </div>
        </section>

        {/* The product, shown rather than described */}
        <section className="mx-auto max-w-5xl px-6 pb-16" aria-label="Example checklist">
          <div className="overflow-hidden rounded-t-2xl border border-line shadow-2xl">
            <div className="flex items-center gap-3 border-b border-line bg-sunken px-4 py-3">
              <div aria-hidden="true" className="flex gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-line-strong opacity-40" />
                <span className="h-2.5 w-2.5 rounded-full bg-line-strong opacity-40" />
                <span className="h-2.5 w-2.5 rounded-full bg-line-strong opacity-40" />
              </div>
              <p className="flex-1 text-center font-mono text-xs text-subtle">
                nasuru.com/applications/hwr-berlin
              </p>
            </div>

            <div className="bg-surface px-6 py-7 sm:px-8">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <h2 className="font-display text-xl font-bold text-ink">
                    HWR Berlin — International Business Management
                  </h2>
                  <p className="mt-0.5 text-sm text-muted">Winter 2027 intake · Collecting documents</p>
                </div>
                <p className="text-sm text-muted">
                  <span className="font-display text-xl font-bold text-ink">9</span> of 17 verified
                </p>
              </div>

              <div
                role="img"
                aria-label="9 of 17 documents verified, 53 percent"
                className="mt-3 h-2 w-full overflow-hidden rounded-full bg-sunken"
              >
                <div className="h-full rounded-full bg-accent" style={{ width: "53%" }} />
              </div>
              <p className="mt-2 text-xs text-subtle">
                13 uploaded · 9 verified. The bar counts verified documents only, so it moves once our team has
                checked each one.
              </p>

              <ul className="mt-6 divide-y divide-line overflow-hidden rounded-xl border border-line">
                <li className="flex items-start gap-4 p-4">
                  <svg aria-hidden="true" viewBox="0 0 24 24" className="mt-0.5 h-5 w-5 shrink-0 text-success" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" /><path d="m8.5 12.5 2.5 2.5 5-5" />
                  </svg>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-ink">Proof of financial resources (blocked account)</p>
                    <p className="mt-0.5 text-sm text-muted">
                      Blocked account confirmation covering one year of living costs.
                    </p>
                  </div>
                  <span className="rounded-full bg-success-bg px-2.5 py-1 text-xs font-semibold whitespace-nowrap text-success">
                    Verified
                  </span>
                </li>

                <li className="flex items-start gap-4 bg-warning-bg p-4">
                  <svg aria-hidden="true" viewBox="0 0 24 24" className="mt-0.5 h-5 w-5 shrink-0 text-warning" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <circle cx="12" cy="12" r="10" /><path d="M12 8v4M12 16h.01" />
                  </svg>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-ink">WAEC/NECO certificate and results</p>
                    <p className="mt-0.5 text-sm text-muted">Scanned original, plus the online result printout.</p>
                    {/* A rejection always carries its reason — the server refuses
                        one without it, so this is what a student really sees. */}
                    <p className="mt-2.5 rounded-lg bg-surface px-3 py-2.5 text-sm text-warning">
                      <strong className="font-semibold">Needs another look:</strong> The image is too blurred to read
                      the grades. Please re-scan it in better light.
                    </p>
                  </div>
                  <span className="rounded-full bg-surface px-2.5 py-1 text-xs font-semibold whitespace-nowrap text-warning">
                    Needs redoing
                  </span>
                </li>

                <li className="flex items-start gap-4 p-4">
                  <svg aria-hidden="true" viewBox="0 0 24 24" className="mt-0.5 h-5 w-5 shrink-0 text-info" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" />
                  </svg>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-ink">
                      German A2 certificate{" "}
                      <span className="font-normal text-subtle">— admission minimum</span>
                    </p>
                    <p className="mt-0.5 text-sm text-muted">
                      A2 is the admission minimum; B1 is recommended before travel.
                    </p>
                  </div>
                  <span className="rounded-full bg-info-bg px-2.5 py-1 text-xs font-semibold whitespace-nowrap text-info">
                    In review
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </section>

        {/* Journey */}
        <section id="journey" className="border-y border-line bg-sunken py-16" aria-labelledby="journey-heading">
          <div className="mx-auto max-w-6xl px-6">
            <h2 id="journey-heading" className="font-display text-center text-3xl font-extrabold tracking-tight text-ink">
              What the whole thing looks like
            </h2>
            <p className="mx-auto mt-3 mb-10 max-w-2xl text-center text-lg text-muted">
              Five stages, eighteen months to two years end to end. We tell you which stage you’re in and what is
              holding it up.
            </p>
            <div className="overflow-hidden rounded-2xl border border-line bg-surface">
              <StudentJourney />
            </div>
          </div>
        </section>

        {/* Three things a spreadsheet cannot do */}
        <section className="mx-auto max-w-6xl px-6 py-16">
          <div className="grid gap-6 sm:grid-cols-3">
            {[
              {
                title: "Upload once, not five times",
                body: "Applying to four universities does not mean scanning your passport four times. One upload satisfies that requirement on every application at once.",
                icon: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></>,
              },
              {
                title: "Progress that means something",
                body: "The bar counts verified documents, not uploaded ones. You will never be told you are nearly done on the strength of files nobody has checked.",
                icon: <><path d="M3 3v18h18" /><path d="m7 14 4-4 3 3 5-6" /></>,
              },
              {
                title: "Rejections come with reasons",
                body: "Never just “rejected”. Always what was wrong and what to do about it — by email, WhatsApp or Telegram, whichever you choose.",
                icon: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
              },
            ].map((item) => (
              <div key={item.title} className="rounded-xl border border-line p-7">
                <svg aria-hidden="true" viewBox="0 0 24 24" className="mb-4 h-6 w-6 text-accent" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  {item.icon}
                </svg>
                <h3 className="font-display text-lg font-bold text-ink">{item.title}</h3>
                <p className="mt-2 text-muted">{item.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* The requirements */}
        <section id="checklist" className="border-t border-line bg-sunken py-16">
          <div className="mx-auto max-w-6xl px-6">
            <h2 className="font-display text-3xl font-extrabold tracking-tight text-ink">
              What a German application actually needs
            </h2>
            <p className="mt-3 max-w-3xl text-lg text-muted">
              Your checklist is generated from the requirement set of the specific university and programme you choose
              — not a generic list. This is the shape of it.
            </p>
            <dl className="mt-8 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
              {CHECKLIST_CATEGORIES.map((category, index) => (
                <div key={category.name} className="bg-surface p-6">
                  <dt className="font-display flex items-baseline gap-2.5 text-base font-bold text-ink">
                    <span className="font-mono text-sm text-accent">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    {category.name}
                  </dt>
                  <dd className="mt-2 text-sm leading-relaxed text-muted">{category.detail}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        {/* Fees and the honest limits */}
        <section id="fees" className="mx-auto max-w-6xl px-6 py-16">
          <div className="grid gap-12 lg:grid-cols-[1fr_1.15fr]">
            <div>
              <p className="text-xs font-bold tracking-[0.14em] text-accent uppercase">One price</p>
              <p className="font-display mt-3 text-5xl font-extrabold tracking-tight text-ink">
                {ACCESS_FEE.formatted}
              </p>
              <p className="mt-1 text-muted">Once. Stated here, before you create an account.</p>

              <div className="mt-6 rounded-xl bg-success-bg p-5 text-success">
                <p className="leading-relaxed">
                  <strong className="font-semibold">
                    {REFUND.coolingOffDays}-day full refund
                  </strong>{" "}
                  as long as we haven’t yet reviewed one of your documents. Your checklist shows you exactly when that
                  has happened.
                </p>
              </div>

              <p className="mt-5 leading-relaxed text-muted">
                uni-assist fees, IELTS, the blocked account deposit and visa fees are paid by you, directly to those
                bodies. We tell you what each costs before you commit to it.
              </p>
              <p className="mt-4 text-sm text-subtle">
                Read the{" "}
                <Link href="/refund-policy" className="text-ink underline underline-offset-2">refund policy</Link>{" "}
                and{" "}
                <Link href="/terms" className="text-ink underline underline-offset-2">terms</Link> before you pay.
              </p>
            </div>

            <div className="rounded-xl border border-line bg-sunken p-8">
              <h2 className="font-display text-2xl font-extrabold tracking-tight text-ink">
                Three things we will never say
              </h2>
              <dl className="mt-5 space-y-5">
                {NOT_INCLUDED.map((item) => (
                  <div key={item.claim}>
                    <dt className="font-semibold text-ink">{item.claim}</dt>
                    <dd className="mt-1 leading-relaxed text-muted">{item.truth}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-6 text-sm leading-relaxed text-subtle">
                We put this on the front page because the people we work with have usually already been burned by
                someone who did not.
              </p>
            </div>
          </div>
        </section>

        {/* Close */}
        <section className="border-t border-line bg-ink py-16 text-center" style={{ color: "var(--canvas)" }}>
          <div className="mx-auto max-w-3xl px-6">
            <h2 className="font-display text-3xl font-extrabold tracking-tight" style={{ color: "var(--canvas)" }}>
              See what your application actually needs
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-lg opacity-80">
              Pick your university, answer a few questions, and get the real checklist. Ten minutes, and you can save
              and come back.
            </p>
            <Link
              href="/signup"
              className="mt-8 inline-block rounded-lg bg-accent px-8 py-3.5 text-base font-bold text-on-accent transition hover:bg-accent-hover"
            >
              Create your account
            </Link>
            <p className="mt-6 text-sm opacity-70">
              Questions first? {CONTACT.phone} (call or WhatsApp) · {CONTACT.email} · {CONTACT.hours}
            </p>
          </div>
        </section>
      </main>

      <footer className="border-t border-line bg-canvas py-10">
        <div className="mx-auto max-w-6xl px-6">
          <nav aria-label="Policies" className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
            <Link href="/privacy" className="text-muted hover:text-ink">Privacy policy</Link>
            <Link href="/terms" className="text-muted hover:text-ink">Terms of service</Link>
            <Link href="/refund-policy" className="text-muted hover:text-ink">Refund policy</Link>
            <Link href="/contact" className="text-muted hover:text-ink">Contact</Link>
          </nav>
          <p className="mt-5 max-w-3xl text-sm leading-relaxed text-subtle">
            {COMPANY.legalName} · RC <span className="font-mono">{COMPANY.registrationNumber}</span> ·{" "}
            {formattedAddress()}. Your documents are stored encrypted, are never publicly linkable, and are processed
            in line with the Nigeria Data Protection Regulation.
          </p>
        </div>
      </footer>
    </div>
  );
}
