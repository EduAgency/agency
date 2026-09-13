import Link from "next/link";
import { StudentJourney } from "@/components/StudentJourney";
import { SiteFooter, SiteHeader } from "@/components/marketing/SiteChrome";
import { HomepageGuides } from "@/components/marketing/HomepageGuides";
import { getPricing, isPriceKnown } from "@/lib/pricing";
import { ACCREDITATION, CONTACT, REFUND, SERVICES, isPending } from "@/lib/company";

/**
 * Landing page.
 *
 * The offer: find tuition-free universities abroad, say exactly what each one
 * requires, write the CV and motivation letter with the student, and consult
 * on the visa once an offer exists. One fee, and no commission from anyone.
 *
 * **No country or university is named here on purpose.** The matched shortlist
 * is the thing being sold; giving it away on the landing page would leave
 * nothing to pay for.
 *
 * That creates the problem this page is mostly built to solve. To a reader who
 * has already been taken by an agency, "pay first, find out after" is exactly
 * what a scam looks like — so the page has to earn the fee without the one
 * piece of evidence it cannot show. It does that four ways: the certification
 * (published with a verifiable reference the moment we hold it), the refund
 * stated as the answer to that exact fear, the limits of what any agent can
 * promise put on the front page, and a product that lets the student watch
 * every document and every decision rather than being told it is progressing.
 *
 * "Tuition-free" also never shades into "free". The costs a free place does
 * not remove get their own section, because budgeting for zero is how students
 * come unstuck weeks before an intake.
 */

const ORDER = [
  {
    step: "First",
    title: "Admission",
    body: "Everything starts here. A university has to accept you before any visa conversation is real — and no agent, anywhere, can shortcut that.",
  },
  {
    step: "Then",
    title: "The visa",
    body: "Once you hold an offer, we prepare the visa file with you: proof of funds, health checks, insurance, accommodation, the appointment.",
  },
];

const NOT_INCLUDED = [
  {
    claim: "“Guaranteed admission.”",
    truth:
      "The university decides. A complete, well-argued application is the only honest advantage anyone can give you.",
  },
  {
    claim: "“Guaranteed visa.”",
    truth:
      "The embassy decides. No agent influences that, and any that says otherwise is selling you something else.",
  },
  {
    claim: "“Pay us millions and leave it to us.”",
    truth:
      "You will write your own motivation letter, with our help. You will see every document and every decision. An agent who wants you out of the process is usually hiding how little of it there is.",
  },
];

export default async function Home() {
  const accreditationPending = isPending(ACCREDITATION.body);

  // Every figure on this page comes from /api/pricing/ — the fee we charge and
  // the costs a student still faces. Both used to be constants in company.ts,
  // and the fee in particular was also typed into the checkout button, where it
  // was free to disagree with what the gateway actually charged.
  const pricing = await getPricing();
  const fee = pricing.access_fee;
  const priceKnown = isPriceKnown(pricing);

  return (
    <div className="bg-canvas">
      <SiteHeader />

      <main>
        {/* Hero */}
        <section className="mx-auto max-w-6xl px-6 py-16 text-center sm:py-20">
          <p className="text-xs font-bold tracking-[0.14em] text-accent uppercase">
            {ACCREDITATION.credential} · Serving students across Nigeria
          </p>
          <h1 className="font-display mx-auto mt-4 max-w-4xl text-4xl leading-[1.08] font-extrabold tracking-tight text-balance text-ink sm:text-5xl">
            There are good universities abroad that charge no tuition. We help you get into one.
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg leading-relaxed text-muted">
            We find the tuition-free schools that will take your qualifications, tell you exactly
            what each one requires, write your CV and motivation letter with you, and consult on the
            visa once you have an offer.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/signup"
              className="rounded-lg bg-accent px-7 py-3.5 text-base font-bold text-on-accent transition hover:bg-accent-hover"
            >
              See my matched schools{priceKnown ? ` — ${fee.formatted} once` : ""}
            </Link>
            <span className="text-sm text-subtle">
              Refundable for {REFUND.coolingOffDays} days. No subscription, no commission.
            </span>
          </div>

          {/* The most load-bearing claim on the page, so it either carries a
              reference a student can check, or it says plainly it is pending. */}
          <div className="mx-auto mt-10 max-w-2xl rounded-xl border border-line bg-sunken p-5 text-left sm:flex sm:items-center sm:gap-5">
            <svg
              aria-hidden="true"
              viewBox="0 0 24 24"
              className="mb-3 h-9 w-9 shrink-0 text-accent sm:mb-0"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 2 4 6v6c0 5 3.4 8.9 8 10 4.6-1.1 8-5 8-10V6z" />
              <path d="m9 12 2 2 4-4" />
            </svg>
            <div>
              <p className="font-display font-bold text-ink">{ACCREDITATION.credential}</p>
              {accreditationPending ? (
                <p className="mt-1 text-sm leading-relaxed text-muted">
                  Our certificate and its reference number will be published here, with a link so
                  you can verify it directly with the awarding body. Until then, ask us for it — we
                  will send it to you.
                </p>
              ) : (
                <p className="mt-1 text-sm leading-relaxed text-muted">
                  Certified by {ACCREDITATION.body} since {ACCREDITATION.since}. Reference{" "}
                  <span className="font-mono text-ink">{ACCREDITATION.reference}</span> —{" "}
                  <a
                    href={ACCREDITATION.verifyUrl}
                    className="text-ink underline underline-offset-2"
                  >
                    verify it independently
                  </a>
                  .
                </p>
              )}
            </div>
          </div>
        </section>

        {/* What we do */}
        <section id="what-we-do" className="border-y border-line bg-sunken py-16">
          <div className="mx-auto max-w-6xl px-6">
            <h2 className="font-display text-3xl font-extrabold tracking-tight text-ink">
              Four things, and we do them with you
            </h2>
            <p className="mt-3 max-w-3xl text-lg text-muted">
              Not &ldquo;we handle everything&rdquo;. You will write your own motivation letter —
              with us, until it is right. An agent who wants you out of the process is usually
              hiding how little of it there is.
            </p>
            <ol className="mt-8 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2">
              {SERVICES.map((service, index) => (
                <li key={service.title} className="bg-surface p-7">
                  <p className="font-mono text-sm font-bold text-accent">
                    {String(index + 1).padStart(2, "0")}
                  </p>
                  <h3 className="font-display mt-2 text-lg font-bold text-ink">{service.title}</h3>
                  <p className="mt-2 leading-relaxed text-muted">{service.detail}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Sequencing — the expectation most students arrive with is wrong */}
        <section className="mx-auto max-w-6xl px-6 py-16">
          <div className="grid gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
            <div>
              <h2 className="font-display text-3xl font-extrabold tracking-tight text-ink">
                Admission first. Then the visa.
              </h2>
              <p className="mt-3 leading-relaxed text-muted">
                Most people arrive asking us about visas. That conversation cannot start until a
                university has accepted you, so almost everything we do together happens before it —
                and the quality of your application is the part you can still change.
              </p>
            </div>
            <ol className="grid gap-5 sm:grid-cols-2">
              {ORDER.map((stage) => (
                <li key={stage.title} className="rounded-xl border border-line p-6">
                  <p className="text-xs font-bold tracking-[0.14em] text-accent uppercase">
                    {stage.step}
                  </p>
                  <h3 className="font-display mt-2 text-lg font-bold text-ink">{stage.title}</h3>
                  <p className="mt-2 leading-relaxed text-muted">{stage.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* The honest answer to "why would I pay before I see the list?" */}
        <section className="border-y border-line bg-sunken py-16">
          <div className="mx-auto max-w-3xl px-6 text-center">
            <h2 className="font-display text-3xl font-extrabold tracking-tight text-ink">
              &ldquo;So what am I actually paying for, before I see anything?&rdquo;
            </h2>
            <p className="mt-4 text-lg leading-relaxed text-muted">
              A fair question, and one you should ask every agent. The shortlist is the work —
              knowing which universities charge no tuition, which of those are any good in your
              subject, and which will accept a Nigerian qualification. Publishing it here would be
              publishing the thing you are paying for.
            </p>
            <p className="mt-4 text-lg leading-relaxed text-muted">
              So the risk sits with us instead:
            </p>
            <div className="mt-6 rounded-xl bg-success-bg p-6 text-left text-success">
              <p className="font-display text-lg font-bold">
                {priceKnown ? `Pay ${fee.formatted}.` : "Pay the access fee."} See your matched
                schools and what each one requires. If it is not worth it, ask for your money back
                within {REFUND.coolingOffDays} days.
              </p>
              <p className="mt-3 leading-relaxed">
                No reason needed, and we will not try to talk you out of it. The only condition is
                that we have not already reviewed one of your documents — and your checklist shows
                you exactly when that happens.
              </p>
            </div>
            <p className="mt-6 text-muted">
              That is {priceKnown ? fee.formatted : "one fee"} to find out, against a decision worth
              years of your life.
            </p>
          </div>
        </section>

        {/* Tuition-free is not free.
            Hidden entirely when there are no cost rows configured: a table with a
            header and nothing under it reads as a broken page, and the argument
            this section makes is worth nothing without the figures. Add rows in
            the admin, or run `make pricing`. */}
        {pricing.costs.length > 0 ? (
          <section id="costs" className="mx-auto max-w-6xl px-6 py-16">
            <div className="grid gap-10 lg:grid-cols-[1fr_1.2fr] lg:items-start">
              <div>
                <h2 className="font-display text-3xl font-extrabold tracking-tight text-ink">
                  Tuition-free is not the same as free
                </h2>
                <p className="mt-3 leading-relaxed text-muted">
                  No tuition is a genuine saving — usually the largest single one available to a
                  Nigerian student. It is not the whole bill. You should hear these figures from us
                  now rather than discover them weeks before an intake.
                </p>
                <p className="mt-4 leading-relaxed text-muted">
                  None of this money comes to us. We tell you what each item costs before you commit
                  to it.
                </p>
              </div>
              <div
                className="overflow-x-auto rounded-xl border border-line"
                tabIndex={0}
                role="region"
                aria-label="Costs a tuition-free place does not remove"
              >
                <table className="w-full min-w-[30rem] text-left">
                  <caption className="sr-only">Costs a tuition-free place does not remove.</caption>
                  <thead>
                    <tr className="border-b border-line bg-sunken">
                      <th scope="col" className="px-5 py-3 text-sm font-semibold text-ink">
                        You will still pay for
                      </th>
                      <th scope="col" className="px-5 py-3 text-sm font-semibold text-ink">
                        Roughly
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {pricing.costs.map((cost) => (
                      <tr key={cost.id} className="border-b border-line last:border-0">
                        <th scope="row" className="px-5 py-4 font-normal">
                          <span className="font-medium text-ink">{cost.label}</span>
                          <span className="mt-0.5 block text-sm text-subtle">{cost.note}</span>
                        </th>
                        <td className="px-5 py-4 align-top">
                          {/* `amount` has already been replaced with "ask us" by
                            the API when nobody has verified the figure inside the
                            staleness window. A stale number here is worse than
                            none — a student budgets against it. */}
                          {cost.is_verified ? (
                            <span className="font-mono text-sm text-muted">{cost.amount}</span>
                          ) : (
                            <span className="rounded-full bg-warning-bg px-2.5 py-1 text-xs font-semibold whitespace-nowrap text-warning">
                              {cost.amount}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        ) : null}

        {/* Transparency, made concrete */}
        <section className="border-y border-line bg-sunken py-16" aria-labelledby="tracker-heading">
          <div className="mx-auto max-w-5xl px-6">
            <div className="text-center">
              <h2
                id="tracker-heading"
                className="font-display text-3xl font-extrabold tracking-tight text-ink"
              >
                You watch the whole thing happen
              </h2>
              <p className="mx-auto mt-3 max-w-2xl text-lg text-muted">
                Every document, its status, and — when something is rejected — exactly why, in
                writing. Not a monthly phone call where you are told it is progressing.
              </p>
            </div>

            <div className="mt-10 overflow-hidden rounded-t-2xl border border-line bg-surface shadow-2xl">
              <div className="flex items-center gap-3 border-b border-line bg-sunken px-4 py-3">
                <div aria-hidden="true" className="flex gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-line-strong opacity-40" />
                  <span className="h-2.5 w-2.5 rounded-full bg-line-strong opacity-40" />
                  <span className="h-2.5 w-2.5 rounded-full bg-line-strong opacity-40" />
                </div>
                <p className="flex-1 text-center font-mono text-xs text-subtle">
                  nasuru.com/applications
                </p>
                <span className="rounded bg-info-bg px-2 py-0.5 text-xs font-semibold text-info">
                  Example
                </span>
              </div>

              <div className="px-6 py-7 sm:px-8">
                <div className="flex flex-wrap items-end justify-between gap-4">
                  <div>
                    <h3 className="font-display text-xl font-bold text-ink">
                      MSc International Business
                    </h3>
                    <p className="mt-0.5 text-sm text-muted">
                      Public university, no tuition · Collecting documents
                    </p>
                  </div>
                  <p className="text-sm text-muted">
                    <span className="font-display text-xl font-bold text-ink">9</span> of 17
                    verified
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
                  13 uploaded · 9 verified. The bar counts verified documents only, so it moves once
                  our team has checked each one.
                </p>

                <ul className="mt-6 divide-y divide-line overflow-hidden rounded-xl border border-line">
                  <li className="flex items-start gap-4 p-4">
                    <svg
                      aria-hidden="true"
                      viewBox="0 0 24 24"
                      className="mt-0.5 h-5 w-5 shrink-0 text-success"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <circle cx="12" cy="12" r="10" />
                      <path d="m8.5 12.5 2.5 2.5 5-5" />
                    </svg>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-ink">Motivation letter — final draft</p>
                      <p className="mt-0.5 text-sm text-muted">
                        Written with your counsellor, specific to this programme.
                      </p>
                    </div>
                    <span className="rounded-full bg-success-bg px-2.5 py-1 text-xs font-semibold whitespace-nowrap text-success">
                      Verified
                    </span>
                  </li>

                  <li className="flex items-start gap-4 bg-warning-bg p-4">
                    <svg
                      aria-hidden="true"
                      viewBox="0 0 24 24"
                      className="mt-0.5 h-5 w-5 shrink-0 text-warning"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                    >
                      <circle cx="12" cy="12" r="10" />
                      <path d="M12 8v4M12 16h.01" />
                    </svg>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-ink">WAEC/NECO certificate and results</p>
                      <p className="mt-0.5 text-sm text-muted">
                        Scanned original, plus the online result printout.
                      </p>
                      {/* A rejection always carries its reason — the server refuses
                          one without it, so this is what a student really sees. */}
                      <p className="mt-2.5 rounded-lg bg-surface px-3 py-2.5 text-sm text-warning">
                        <strong className="font-semibold">Needs another look:</strong> The image is
                        too blurred to read the grades. Please re-scan it in better light.
                      </p>
                    </div>
                    <span className="rounded-full bg-surface px-2.5 py-1 text-xs font-semibold whitespace-nowrap text-warning">
                      Needs redoing
                    </span>
                  </li>

                  <li className="flex items-start gap-4 p-4">
                    <svg
                      aria-hidden="true"
                      viewBox="0 0 24 24"
                      className="mt-0.5 h-5 w-5 shrink-0 text-info"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                    >
                      <circle cx="12" cy="12" r="10" />
                      <path d="M12 6v6l4 2" />
                    </svg>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-ink">
                        Certified translation — transcript{" "}
                        <span className="font-normal text-subtle">— arranged by us</span>
                      </p>
                      <p className="mt-0.5 text-sm text-muted">
                        Sworn translator, accepted by the university.
                      </p>
                    </div>
                    <span className="rounded-full bg-info-bg px-2.5 py-1 text-xs font-semibold whitespace-nowrap text-info">
                      In review
                    </span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* Journey */}
        <section id="journey" className="py-16" aria-labelledby="journey-heading">
          <div className="mx-auto max-w-6xl px-6">
            <h2
              id="journey-heading"
              className="font-display text-center text-3xl font-extrabold tracking-tight text-ink"
            >
              What the whole thing looks like
            </h2>
            <p className="mx-auto mt-3 mb-10 max-w-2xl text-center text-lg text-muted">
              From the first conversation to the day you land. We tell you which stage you are in
              and what is holding it up.
            </p>
            <div className="overflow-hidden rounded-2xl border border-line bg-surface">
              <StudentJourney />
            </div>
          </div>
        </section>

        {/* Fee */}
        {/* Renders nothing when the setting is off or there are no live posts. */}
        <HomepageGuides />

        <section id="fees" className="border-t border-line bg-sunken py-16">
          <div className="mx-auto max-w-6xl px-6">
            <div className="grid items-start gap-12 lg:grid-cols-[1fr_1.1fr]">
              <div>
                <p className="text-xs font-bold tracking-[0.14em] text-accent uppercase">
                  What we charge
                </p>
                <p className="font-display mt-3 text-5xl font-extrabold tracking-tight text-ink">
                  {priceKnown ? fee.formatted : "—"}
                </p>
                <p className="mt-1 text-muted">
                  Once. Not a deposit, not a percentage, not a monthly fee.
                </p>

                <div className="mt-6 rounded-xl border border-line bg-surface p-5">
                  <p className="leading-relaxed text-muted">
                    We take no commission from any university, so the shortlist you get is the one
                    that suits you rather than the one that pays us.{" "}
                    <strong className="font-semibold text-ink">
                      We have not found a Nigerian agent who charges less
                    </strong>{" "}
                    — if you find one, we would genuinely like to know.
                  </p>
                </div>

                <p className="mt-5 leading-relaxed text-muted">
                  Our fee is the only money that comes to us. Application fees, tests, deposits and
                  visa charges are paid by you, directly to those bodies — we never take a cut of
                  any of them.
                </p>
                <p className="mt-4 text-sm text-subtle">
                  Read the{" "}
                  <Link href="/refund-policy" className="text-ink underline underline-offset-2">
                    refund policy
                  </Link>{" "}
                  and{" "}
                  <Link href="/terms" className="text-ink underline underline-offset-2">
                    terms
                  </Link>{" "}
                  before you pay.
                </p>
              </div>

              <div className="rounded-xl border border-line bg-surface p-8">
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
                  We put this on the front page because the people we work with have usually already
                  been burned by someone who did not.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Close */}
        <section
          className="border-t border-line bg-ink py-16 text-center"
          style={{ color: "var(--canvas)" }}
        >
          <div className="mx-auto max-w-3xl px-6">
            <h2
              className="font-display text-3xl font-extrabold tracking-tight"
              style={{ color: "var(--canvas)" }}
            >
              Tell us what you studied and what you can fund
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-lg opacity-80">
              Ten minutes, and you will know which tuition-free universities are realistic for you —
              or that they are not, which is worth knowing too.
            </p>
            <Link
              href="/signup"
              className="mt-8 inline-block rounded-lg bg-accent px-8 py-3.5 text-base font-bold text-on-accent transition hover:bg-accent-hover"
            >
              Create your account
            </Link>
            <p className="mt-6 text-sm opacity-70">
              Questions first? {CONTACT.phone} (call or WhatsApp) · {CONTACT.email} ·{" "}
              {CONTACT.hours}
            </p>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
