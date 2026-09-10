import Link from "next/link";
import { Clause, LegalDocument } from "@/components/legal";
import { COMPANY, CONTACT, DATA_PROTECTION, formattedAddress } from "@/lib/company";

/**
 * Deliberately not a contact form.
 *
 * A form here would need its own endpoint, its own spam handling and its own
 * inbox before it was worth anything, and a form that silently drops messages
 * is worse than a published address. Students already have in-platform
 * messaging with their counsellor once signed in; this page is for everyone
 * else — and for the data-protection requests the privacy policy points here.
 */

export const metadata = {
  title: "Contact — Nasuru",
  description: "How to reach Nasuru, and what to expect back.",
};

export default function ContactPage() {
  return (
    <LegalDocument
      title="Contact us"
      updated="10 September 2026"
      summary="If you already have an account, the fastest route is your counsellor inside the platform — they can see your checklist while they answer. Everything else comes here."
    >
      <Clause heading="If you have an account">
        <p>
          Sign in and message your counsellor from your dashboard. They can see your applications
          and your checklist, so you will not have to explain your situation from scratch.
        </p>
        <p>
          <Link href="/login" className="underline underline-offset-2">
            Sign in
          </Link>
        </p>
      </Clause>

      <Clause heading="Everyone else">
        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-[auto_1fr]">
          <dt className="font-medium text-ink">WhatsApp or call</dt>
          <dd>
            <a href={CONTACT.whatsappHref} className="underline underline-offset-2">
              {CONTACT.phone}
            </a>{" "}
            on WhatsApp, or{" "}
            <a href={CONTACT.phoneHref} className="underline underline-offset-2">
              call the same number
            </a>
            .
          </dd>

          <dt className="font-medium text-ink">Email</dt>
          <dd>
            <a href={`mailto:${CONTACT.email}`} className="underline underline-offset-2">
              {CONTACT.email}
            </a>
          </dd>

          <dt className="font-medium text-ink">Office</dt>
          <dd>
            {formattedAddress()}
            <br />
            {COMPANY.address.country}
          </dd>

          <dt className="font-medium text-ink">Hours</dt>
          <dd>{CONTACT.hours}</dd>
        </dl>
        <p>
          Messages sent outside those hours are answered the next working day. We do not charge for
          asking a question before you sign up.
        </p>
      </Clause>

      <Clause heading="Data protection requests">
        <p>
          To ask for a copy of your data, correct it, or have your account and documents deleted,
          email{" "}
          <a
            href={`mailto:${DATA_PROTECTION.contactEmail}?subject=${encodeURIComponent(DATA_PROTECTION.subjectLine)}`}
            className="underline underline-offset-2"
          >
            {DATA_PROTECTION.contactEmail}
          </a>{" "}
          with &ldquo;{DATA_PROTECTION.subjectLine}&rdquo; in the subject line, so it reaches our
          Data Protection Officer directly.
        </p>
        <p>
          Say which of those you want, and write from the email address on your account so we can be
          sure the request is really from you. We respond within {DATA_PROTECTION.responseDays}{" "}
          days, as the NDPR requires.
        </p>
      </Clause>

      <Clause heading="Reporting a problem with a payment">
        <p>
          Include the payment reference and the email address on your account. We reconcile against
          the payment provider&apos;s own record rather than what your browser showed, so we can
          usually resolve a missing payment without you needing to prove anything.
        </p>
      </Clause>

      <Clause heading="Reporting a security issue">
        <p>
          Email{" "}
          <a
            href={`mailto:${CONTACT.email}?subject=${encodeURIComponent("Security report")}`}
            className="underline underline-offset-2"
          >
            {CONTACT.email}
          </a>{" "}
          with &ldquo;Security report&rdquo; in the subject line.
        </p>
        <p>
          If you are a security researcher: we will not pursue legal action over a good-faith report
          made through this address, provided you do not access, modify or retain another
          person&apos;s data, and give us reasonable time to fix the issue before publishing.
        </p>
      </Clause>

      <Clause heading="Company details">
        <p>
          {COMPANY.legalName}, registered in Nigeria, company registration number{" "}
          <span className="font-mono">{COMPANY.registrationNumber}</span>.
        </p>
        <p>{formattedAddress()}.</p>
      </Clause>
    </LegalDocument>
  );
}
