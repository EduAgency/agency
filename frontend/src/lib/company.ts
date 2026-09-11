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

export const ACCESS_FEE = {
  amount: 5000,
  currency: "NGN",
  /** Rendered through Intl so the symbol and grouping are never hand-typed. */
  get formatted() {
    return new Intl.NumberFormat("en-NG", {
      style: "currency",
      currency: this.currency,
      maximumFractionDigits: 0,
    }).format(this.amount);
  },
} as const;

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
  { name: "Meta (WhatsApp Business)", purpose: "Optional WhatsApp updates", location: "United States" },
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
