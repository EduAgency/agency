import Link from "next/link";
import { StudentJourney } from "@/components/StudentJourney";
import {
  ACCESS_FEE,
  ACCREDITATION,
  COMPANY,
  CONTACT,
  DESTINATIONS,
  REFUND,
  formattedAddress,
  isPending,
} from "@/lib/company";

/**
 * Landing page.
 *
 * Positioning: an international education agent, certified for the UK, working
 * with students anywhere in Nigeria. The certification is the strongest thing
 * on the page and so gets the most careful handling — see the credential block
 * below, which renders an honest "pending" state rather than an unverifiable
 * badge until the real certificate details are in `lib/company.ts`.
 *
 * The stance from earlier versions is unchanged (plan §9): the fee is stated
 * before signup rather than revealed at checkout, there are no countdown
 * timers or invented placement counts, and the limits of what an agent can
 * promise are on the front page. This audience has usually been burned by
 * someone who did neither.
 */

const CHECKLIST_CATEGORIES = [
  {
    name: "Documents & transcripts",
    detail: "Passport, WAEC/NECO, transcripts covering every completed semester, CV, translations.",
  },
  {
    name: "English proof",
    detail:
      "IELTS, TOEFL or a UKVI-approved test. Which one counts depends on the country and the course — we confirm yours in writing before you book.",
  },
  {
    name: "Other languages",
    detail: "German, French or another language of instruction, where the country asks for it.",
  },
  {
    name: "Application forms",
    detail: "University portals, UCAS or uni-assist, and the personal statement that goes with them.",
  },
  {
    name: "Financial evidence",
    detail:
      "Bank statements, sponsorship letters, a blocked account. The rules on how long money must be held differ by country and catch people out.",
  },
  {
    name: "Visa & relocation",
    detail: "Visa file, health surcharge, TB test where required, insurance, accommodation.",
  },
  {
    name: "Spouse & family",
    detail:
      "Dependant applications, with their own documents and their own timeline. Most agents treat this as an afterthought.",
  },
];

/** What the one-time fee actually buys, in the order a student meets it. */
const FEE_INCLUDES = [
  "Every international school open to Nigerian students, with the entry requirements each one really asks for — not a shortlist of whoever pays us commission",
  "A shortlist matched to your grades, your degree and what you can genuinely fund",
  "Your document checklist for each application, built from that university’s own requirement set",
  "Document review with written feedback on anything that needs redoing",
  "Tracking across every application, so you always know what is waiting on whom",
  "The visa file — financial evidence, health checks, insurance, accommodation",
  "Pre-departure and arrival: what to carry, what to register for, what to do in your first week",
  "A counsellor you can reach on WhatsApp, Telegram or email throughout",
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
      "The embassy decides. No agent influences that, and any that says otherwise is selling you something else.",
  },
  {
    claim: "“Limited slots — pay today.”",
    truth:
      "There is no countdown on this page. The real deadlines belong to the universities, and we show you those.",
  },
];

export default function Home() {
  const accreditationPending = isPending(ACCREDITATION.body);

  return (
    <div className="bg-canvas">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div className="flex items-center gap-2.5">
            <span aria-hidden="true" className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--on-accent)" }}>
                <path d="M20 6 9 17l-5-5" />
              </svg>
            </span>
            <div>
              <span className="font-display block text-xl leading-none font-extrabold tracking-tight text-ink">
                Nasuru
              </span>
              <span className="text-xs text-subtle">International education agent</span>
            </div>
          </div>
          <nav aria-label="Main" className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
            <a href="#destinations" className="text-muted hover:text-ink">Where you can study</a>
            <a href="#journey" className="text-muted hover:text-ink">How it works</a>
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
            {ACCREDITATION.credential} · Serving students across Nigeria
          </p>
          <h1 className="font-display mx-auto mt-4 max-w-4xl text-4xl leading-[1.08] font-extrabold tracking-tight text-balance text-ink sm:text-5xl">
            Study abroad without guessing which agent to trust
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg leading-relaxed text-muted">
            One fee opens every international school available to Nigerians, and covers everything you need from
            today until you land on campus — choosing the university, the documents, the visa file, the arrival.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/signup"
              className="rounded-lg bg-accent px-7 py-3.5 text-base font-bold text-on-accent transition hover:bg-accent-hover"
            >
              Find my universities — {ACCESS_FEE.formatted} once
            </Link>
            <span className="text-sm text-subtle">
              Refundable for {REFUND.coolingOffDays} days. No subscription.
            </span>
          </div>

          {/* Credential. The most load-bearing claim on the page, so it either
              carries a reference a student can check, or it says it is pending. */}
          <div className="mx-auto mt-10 max-w-2xl rounded-xl border border-line bg-sunken p-5 text-left sm:flex sm:items-center sm:gap-5">
            <svg aria-hidden="true" viewBox="0 0 24 24" className="mb-3 h-9 w-9 shrink-0 text-accent sm:mb-0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2 4 6v6c0 5 3.4 8.9 8 10 4.6-1.1 8-5 8-10V6z" />
              <path d="m9 12 2 2 4-4" />
            </svg>
            <div>
              <p className="font-display font-bold text-ink">{ACCREDITATION.credential}</p>
              {accreditationPending ? (
                <p className="mt-1 text-sm leading-relaxed text-muted">
                  Our certificate and its reference number will be published here, with a link so you can verify it
                  directly with the awarding body. Until then, ask us for it — we will send it to you.
                </p>
              ) : (
                <p className="mt-1 text-sm leading-relaxed text-muted">
                  Certified by {ACCREDITATION.body} since {ACCREDITATION.since}. Reference{" "}
                  <span className="font-mono text-ink">{ACCREDITATION.reference}</span> —{" "}
                  <a href={ACCREDITATION.verifyUrl} className="text-ink underline underline-offset-2">
                    verify it independently
                  </a>
                  .
                </p>
              )}
            </div>
          </div>
        </section>

        {/* Destinations */}
        <section id="destinations" className="border-y border-line bg-sunken py-16">
          <div className="mx-auto max-w-6xl px-6">
            <h2 className="font-display text-3xl font-extrabold tracking-tight text-ink">
              Good universities you can afford
            </h2>
            <p className="mt-3 max-w-3xl text-lg text-muted">
              &ldquo;Best&rdquo; is not the same as &ldquo;most expensive&rdquo;. We start from what you can fund and
              what your degree qualifies you for, then find the strongest universities inside that — and we tell you
              the one requirement each country&rsquo;s applicants underestimate.
            </p>

            <div className="mt-8 grid gap-5 sm:grid-cols-2">
              {DESTINATIONS.map((destination) => {
                const pending = !destination.confirmed;
                return (
                  <div
                    key={destination.country}
                    className={`rounded-xl border p-6 ${
                      destination.lead ? "border-accent bg-surface" : "border-line bg-surface"
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-3">
                      <h3 className="font-display text-lg font-bold text-ink">
                        {pending ? "Another destination" : destination.country}
                      </h3>
                      {destination.lead && (
                        <span className="rounded-full bg-success-bg px-2.5 py-1 text-xs font-semibold text-success">
                          We are certified here
                        </span>
                      )}
                    </div>
                    {pending ? (
                      <p className="mt-2 leading-relaxed text-muted">
                        Tell us where you are aiming and we will say honestly whether we can help, or point you to
                        someone who can.
                      </p>
                    ) : (
                      <>
                        <p className="mt-2 leading-relaxed text-muted">{destination.note}</p>
                        <p className="mt-3 border-t border-line pt-3 text-sm text-subtle">
                          <span className="font-semibold text-muted">Most underestimated:</span>{" "}
                          {destination.hurdle}
                        </p>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* The product, shown rather than described */}
        <section className="mx-auto max-w-5xl px-6 py-16" aria-labelledby="tracker-heading">
          <div className="text-center">
            <h2 id="tracker-heading" className="font-display text-3xl font-extrabold tracking-tight text-ink">
              Then we track every document to the visa
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-lg text-muted">
              Not a WhatsApp chat and a notes app. One checklist per university, built from its real requirements,
              showing what is verified and what is waiting on whom.
            </p>
          </div>

          <div className="mt-10 overflow-hidden rounded-t-2xl border border-line shadow-2xl">
            <div className="flex items-center gap-3 border-b border-line bg-sunken px-4 py-3">
              <div aria-hidden="true" className="flex gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-line-strong opacity-40" />
                <span className="h-2.5 w-2.5 rounded-full bg-line-strong opacity-40" />
                <span className="h-2.5 w-2.5 rounded-full bg-line-strong opacity-40" />
              </div>
              <p className="flex-1 text-center font-mono text-xs text-subtle">nasuru.com/applications</p>
              <span className="rounded bg-info-bg px-2 py-0.5 text-xs font-semibold text-info">Example</span>
            </div>

            <div className="bg-surface px-6 py-7 sm:px-8">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <h3 className="font-display text-xl font-bold text-ink">
                    MSc International Business — United Kingdom
                  </h3>
                  <p className="mt-0.5 text-sm text-muted">September 2027 intake · Collecting documents</p>
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
                    <p className="font-medium text-ink">Financial evidence — 28 consecutive days</p>
                    <p className="mt-0.5 text-sm text-muted">
                      Statements showing the funds held without dipping below the required balance.
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
                      TB test certificate <span className="font-normal text-subtle">— required for Nigeria</span>
                    </p>
                    <p className="mt-0.5 text-sm text-muted">
                      From a clinic approved by the UK Home Office. Valid for six months.
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
              From the first conversation to the day you land. We tell you which stage you are in and what is holding
              it up.
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
                title: "Anywhere in Nigeria",
                body: "Lagos, Kano, Enugu, Port Harcourt — the whole process runs online, with a counsellor you can reach on WhatsApp or Telegram. You never have to travel to an office to hand in a document.",
                icon: <><circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20" /></>,
              },
              {
                title: "Upload once, not five times",
                body: "Applying to four universities does not mean scanning your passport four times. One upload satisfies that requirement on every application at once.",
                icon: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></>,
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
        <section className="border-t border-line bg-sunken py-16">
          <div className="mx-auto max-w-6xl px-6">
            <h2 className="font-display text-3xl font-extrabold tracking-tight text-ink">
              What every application needs
            </h2>
            <p className="mt-3 max-w-3xl text-lg text-muted">
              The categories are the same wherever you apply. What changes — and what catches people out — is the
              detail inside them. Your checklist is generated from the requirement set of the university and
              programme you actually choose, not a generic list.
            </p>
            <dl className="mt-8 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
              {CHECKLIST_CATEGORIES.map((category, index) => (
                <div key={category.name} className="bg-surface p-6">
                  <dt className="font-display flex items-baseline gap-2.5 text-base font-bold text-ink">
                    <span className="font-mono text-sm text-accent">{String(index + 1).padStart(2, "0")}</span>
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
          <div className="grid items-start gap-12 lg:grid-cols-[1fr_1.15fr]">
            <div>
              <p className="text-xs font-bold tracking-[0.14em] text-accent uppercase">One price</p>
              <p className="font-display mt-3 text-5xl font-extrabold tracking-tight text-ink">
                {ACCESS_FEE.formatted}
              </p>
              <p className="mt-1 text-muted">Once. Not a deposit, not a percentage, not a monthly fee.</p>

              <p className="mt-5 leading-relaxed text-muted">
                It opens the full list of international schools available to Nigerian students, and it covers you all
                the way to campus — every one of the five stages above, not just the application.
              </p>

              <ul className="mt-5 space-y-3">
                {FEE_INCLUDES.map((item) => (
                  <li key={item} className="flex items-start gap-3">
                    <svg aria-hidden="true" viewBox="0 0 24 24" className="mt-0.5 h-5 w-5 shrink-0 text-accent" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M20 6 9 17l-5-5" />
                    </svg>
                    <span className="text-muted">{item}</span>
                  </li>
                ))}
              </ul>

              <div className="mt-6 rounded-xl bg-success-bg p-5 text-success">
                <p className="leading-relaxed">
                  <strong className="font-semibold">{REFUND.coolingOffDays}-day full refund</strong> as long as we
                  have not yet reviewed one of your documents. Your checklist shows you exactly when that has
                  happened.
                </p>
              </div>

              <p className="mt-5 leading-relaxed text-muted">
                Our fee is the only money that comes to us. University application fees, English tests, tuition
                deposits, the health surcharge and visa fees are paid by you, directly to those bodies — we tell you
                what each one costs before you commit to it, and we never take a cut of any of them.
              </p>
              <p className="mt-4 text-sm text-subtle">
                Read the{" "}
                <Link href="/refund-policy" className="text-ink underline underline-offset-2">refund policy</Link>{" "}
                and <Link href="/terms" className="text-ink underline underline-offset-2">terms</Link> before you pay.
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
              Tell us where you want to go
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-lg opacity-80">
              Ten minutes, and you will know which universities are realistic for your grades and your budget. One
              fee from there to campus.
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
