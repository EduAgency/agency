/**
 * Company facts, in one place.
 *
 * These values appear across the landing page, all four policy documents and
 * the checkout flow. Scattering them meant a change of address or support hours
 * had to be found in five files; worse, the policy pages shipped with amber
 * "needs sign-off" blocks where the real values belonged
 * (docs/enterprise-readiness.md, Phase 1).
 *
 * Anything still genuinely undecided is marked `PENDING` below rather than
 * invented, and `scripts/check-launch-ready.mjs` fails a production build while
 * any PENDING value remains — so an unfinished policy cannot ship silently.
 */

/** Marks a value that is a real business decision nobody has made yet. */
export const PENDING = "PENDING:" as const;

export const COMPANY = {
  legalName: "Nasuru.com Limited",
  tradingName: "Nasuru",
  registrationNumber: "9759223",
  address: {
    street: "19 Obashoro Street",
    area: "Oke Odo",
    lga: "Alimosho",
    state: "Lagos State",
    country: "Nigeria",
  },
} as const;

export const CONTACT = {
  email: "support@nasuru.com",
  /** Same line takes calls and WhatsApp. */
  phone: "+234 812 934 1700",
  phoneHref: "tel:+2348129341700",
  whatsappHref: "https://wa.me/2348129341700",
  hours: "Monday to Saturday, 8am to 5pm (West Africa Time)",
} as const;

/**
 * The NDPR requires a contact point for data subject requests, not a published
 * personal name — so requests are routed to the support address marked for the
 * DPO's attention. Publish a named officer here if the business appoints one.
 */
export const DATA_PROTECTION = {
  contactEmail: CONTACT.email,
  subjectLine: "Data protection request",
  responseDays: 30,
} as const;

/**
 * The access fee is NOT here any more.
 *
 * It lives in the database (`apps.payments.pricing.Pricing`) and reaches the
 * frontend through `/api/pricing/` — see `@/lib/pricing`. It moved because there
 * were four copies of it and they were allowed to disagree: the gateway charged
 * one number while the checkout button showed another.
 *
 * Nothing in this file may state a price. If you need one, fetch it.
 */

/**
 * The accreditation the landing page leads with.
 *
 * A certification claim is the single most load-bearing thing on a page aimed
 * at an audience that has been defrauded before — and the easiest to fake. So
 * none of it is written until the certificate is in hand: the body, the
 * reference and the verification link stay PENDING, `check:launch` refuses a
 * production build while they are, and the page renders an honest "pending"
 * state rather than a badge nobody can check.
 */
export const ACCREDITATION = {
  credential: "Certified education agent",
  body: `${PENDING} certifying body`,
  reference: `${PENDING} certificate reference`,
  /** Where a student can independently confirm it. A badge nobody can verify is decoration. */
  verifyUrl: `${PENDING} verification link`,
  since: `${PENDING} year`,
} as const;

/**
 * What the service actually is, in the order a student meets it.
 *
 * Deliberately concrete. "We guide you through the process" is what every
 * agency says; naming the four things we sit down and do is what separates a
 * service from a slogan.
 */
export const SERVICES = [
  {
    title: "Find tuition-free universities with courses worth doing",
    detail:
      "Public universities where international students pay no tuition, narrowed to the ones that teach your subject well and will accept your qualifications. Not a shortlist of whoever pays commission — we take none.",
  },
  {
    title: "Tell you exactly what each one requires",
    detail:
      "Every entry requirement in writing, before you spend a naira on a test or a translation. Including the ones students find out about too late: language levels, credential evaluation, how long money has to sit in an account.",
  },
  {
    title: "Write your CV and motivation letter with you",
    detail:
      "Not a template with your name dropped into it. We draft with you until it argues for you specifically, for that programme — and we arrange certified translations of anything not already in the language the university reads.",
  },
  {
    title: "Consult on the visa application — once you have an offer",
    detail:
      "Proof of funds, health checks, insurance, accommodation, the appointment. We prepare the file with you and stay with it to the decision.",
  },
] as const;

/**
 * The student-cost figures are NOT here any more either.
 *
 * They are `CostEstimate` rows, served by `/api/pricing/`. The reason is the
 * comment that used to sit here: a stale number is worse than none. A database
 * row can carry the date somebody last checked it and stop showing the figure
 * by itself once that goes out of date — a constant in a TypeScript file cannot,
 * and would sit there looking authoritative for two years.
 */

export const REFUND = {
  /** Full refund inside this window, provided no document has been reviewed. */
  coolingOffDays: 14,
  acknowledgeWorkingDays: 2,
  decideWorkingDays: 10,
  /** The gateway's own processing time, which is outside our control. */
  gatewayWorkingDays: "5 to 10",
} as const;

/**
 * Retention schedule. Every period here is a commitment the business has to be
 * able to keep, and the deletion jobs that enforce them are Phase 4 work — so
 * these are stated as policy now and become enforced by code later.
 */
export const RETENTION = [
  {
    what: "Documents you upload",
    period: "24 months after the application they belong to is closed or withdrawn",
    why: "Long enough to reapply or appeal without uploading everything again.",
  },
  {
    what: "Payment records",
    period: "7 years",
    why: "Required for Nigerian tax and audit purposes.",
  },
  {
    what: "Your account",
    period: "Deleted after 24 months with no sign-in",
    why: "We email you twice before anything is deleted.",
  },
  {
    what: "Staff audit logs",
    period: "7 years",
    why: "So we can always answer who accessed your file, and when.",
  },
] as const;

/**
 * Third parties who process data on our behalf. The NDPR requires these to be
 * disclosed, including any transfer outside Nigeria.
 *
 * Only the ones the codebase actually integrates are named. Hosting and the
 * email/messaging provider are deployment choices nobody has made, so they are
 * PENDING rather than guessed at — naming the wrong processor in a published
 * policy is worse than admitting the list is incomplete.
 *
 * Cloudflare R2 is named because the code targets it specifically, but *where*
 * its bucket lives is a creation-time choice that is still open.
 */
export const SUB_PROCESSORS = [
  { name: "Paystack", purpose: "Card and bank payments", location: "Nigeria" },
  { name: "Flutterwave", purpose: "Card and bank payments", location: "Nigeria" },
  { name: "Sentry", purpose: "Error monitoring", location: "United States" },
  {
    name: `${PENDING} hosting provider`,
    purpose: "Running the application",
    location: `${PENDING} region`,
  },
  {
    name: "Cloudflare R2",
    purpose: "Storing your uploaded documents",
    // R2 places data by the bucket's jurisdiction, chosen at creation — not
    // per request. Until that choice is made and recorded, saying where the
    // documents live would be a guess, and this is the clause the NDPR cares
    // most about. See R2_ACCOUNT_ID in backend/.env.example.
    location: `${PENDING} jurisdiction`,
  },
  {
    name: `${PENDING} email provider`,
    purpose: "Sending you updates about your application",
    location: `${PENDING} region`,
  },
  // Only reached for students who connect them; see the preference centre.
  {
    name: "Meta (WhatsApp Business)",
    purpose: "Optional WhatsApp updates",
    location: "United States",
  },
  { name: "Telegram", purpose: "Optional Telegram updates", location: "United Arab Emirates" },
] as const;

export function formattedAddress(): string {
  const { street, area, lga, state } = COMPANY.address;
  return `${street}, ${area}, ${lga}, ${state}`;
}

/** True when a value is still an unmade decision. */
export function isPending(value: string): boolean {
  return value.includes(PENDING);
}
