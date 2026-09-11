import Link from "next/link";
import { Clause, LegalDocument, NeedsSignOff, Points } from "@/components/legal";
import { ScrollableX } from "@/components/ui";
import {
  COMPANY,
  DATA_PROTECTION,
  RETENTION,
  SUB_PROCESSORS,
  formattedAddress,
  isPending,
} from "@/lib/company";

/**
 * Every factual claim here is checked against the code, not aspirational.
 * Where the platform does not yet do something the NDPR requires, the gap is
 * marked rather than papered over — see the sign-off callouts.
 */

export const metadata = {
  title: "Privacy policy — Nasuru",
  description: "What Nasuru collects, why, who sees it, and the rights you hold over it.",
};

export default function PrivacyPage() {
  return (
    <LegalDocument
      title="Privacy policy"
      updated="10 September 2026"
      summary="We handle passports, transcripts and identity documents. This page says exactly what we collect, who inside the company can see it, where it is stored, and what you can make us do with it."
    >
      <Clause heading="Who is responsible for your data">
        <p>
          {COMPANY.legalName} is the data controller. We process personal data under the Nigeria
          Data Protection Act 2023 and the NDPR.
        </p>
        <p>
          Registered in Nigeria, company registration number{" "}
          <span className="font-mono">{COMPANY.registrationNumber}</span>, at {formattedAddress()}.
        </p>
        <p>
          Data protection requests go to{" "}
          <a
            href={`mailto:${DATA_PROTECTION.contactEmail}?subject=${encodeURIComponent(DATA_PROTECTION.subjectLine)}`}
            className="underline underline-offset-2"
          >
            {DATA_PROTECTION.contactEmail}
          </a>
          , marked for the attention of our Data Protection Officer.
        </p>
      </Clause>

      <Clause heading="What we collect">
        <p>When you create an account and use the platform, we hold:</p>
        <Points
          items={[
            <>
              <strong>Account details</strong> — your name, email address, phone number, and the
              date you accepted these terms.
            </>,
            <>
              <strong>Student profile</strong> — date of birth, nationality, country and state of
              residence, and a WhatsApp number if you give us one.
            </>,
            <>
              <strong>Application answers</strong> — everything you enter into our intake and school
              forms, kept against the version of the form you answered.
            </>,
            <>
              <strong>Documents you upload</strong> — passports, transcripts, certificates and any
              other file a school on your list requires.
            </>,
            <>
              <strong>Payment records</strong> — the amount, reference, status and gateway response
              for each payment. We never see or store your card or bank details; those go directly
              to Paystack or Flutterwave.
            </>,
            <>
              <strong>Technical records</strong> — the IP address of your last sign-in, and an audit
              log of actions taken on your account by our staff.
            </>,
          ]}
        />
      </Clause>

      <Clause heading="Why we hold it, and on what basis">
        <Points
          items={[
            <>
              <strong>To provide the service you paid for</strong> — building your checklist,
              reviewing your documents and tracking your applications. Basis: performance of our
              contract with you.
            </>,
            <>
              <strong>To send you updates about your application</strong> — when a document is
              verified or rejected, and when something is waiting on you. Basis: performance of our
              contract.
            </>,
            <>
              <strong>To take payment and prevent fraud</strong> — including checking that referral
              rewards are earned on genuine, confirmed payments. Basis: our legitimate interest in
              running the service and not being defrauded.
            </>,
            <>
              <strong>Marketing</strong> — only if you opted in. You can withdraw at any time and it
              will not affect the service you receive.
            </>,
          ]}
        />
      </Clause>

      <Clause heading="Who can see your documents">
        <p>
          Access inside the company is granted by role, not by seniority. Every staff account
          carries an explicit set of permissions — reviewing documents, managing students, viewing
          payments, exporting data and so on — and each is granted separately.
        </p>
        <p>
          In practice: a document reviewer can open your uploads but cannot reach payment gateway
          credentials; a finance user can see that you paid but has no reason to open your passport
          and is not given the permission to do so.
        </p>
        <p>
          Staff actions on your record are written to an audit log that records who did what and
          when. Passwords, tokens and gateway secrets are stripped from that log before it is
          written.
        </p>
      </Clause>

      <Clause heading="Where your documents are stored">
        <p>
          Uploaded documents are held in private object storage at Cloudflare R2. They are never
          publicly addressable: each time a document is opened, the platform issues a signed link
          that stops working after fifteen minutes. Files are encrypted at rest with AES-256, and
          are not stored on the application server&apos;s own disk.
        </p>
        <p>
          Payment gateway credentials are encrypted in the database with a key held outside it, so a
          database copy alone does not expose them.
        </p>
      </Clause>

      <Clause heading="Who else processes your data">
        <p>
          These companies handle data on our behalf. They may only use it to provide the service to
          us, never for their own purposes.
        </p>
        <ScrollableX label="Sub-processors">
          <table className="w-full min-w-[28rem] text-left text-sm">
            <thead>
              <tr className="border-b border-line">
                <th scope="col" className="py-2 pr-4 font-medium text-ink">
                  Who
                </th>
                <th scope="col" className="py-2 pr-4 font-medium text-ink">
                  What for
                </th>
                <th scope="col" className="py-2 font-medium text-ink">
                  Where
                </th>
              </tr>
            </thead>
            <tbody>
              {SUB_PROCESSORS.map((processor) => (
                <tr key={processor.name} className="border-b border-line last:border-0">
                  <td className="py-2 pr-4">{processor.name}</td>
                  <td className="py-2 pr-4">{processor.purpose}</td>
                  <td className="py-2">{processor.location}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableX>
        {SUB_PROCESSORS.some((p) => isPending(p.name) || isPending(p.location)) && (
          <NeedsSignOff>
            Rows marked PENDING are deployment choices that have not been made. Naming the wrong
            processor in a published policy is worse than an incomplete list, so they stay marked
            until hosting, object storage and the email/SMS provider are chosen. Note that the
            default storage region in the backend config is <code>eu-west-1</code> (Ireland) — any
            region outside Nigeria is an international transfer the NDPR requires you to disclose
            here and to have a lawful basis for.
          </NeedsSignOff>
        )}
      </Clause>

      <Clause heading="Your rights">
        <p>Under the NDPR you can ask us to:</p>
        <Points
          items={[
            "Give you a copy of everything we hold about you.",
            "Correct anything that is wrong.",
            "Delete your account and the documents attached to it.",
            "Send your data to you in a portable format.",
            "Stop sending you marketing, at any time.",
          ]}
        />
        <p>
          To make any of these requests, email{" "}
          <a
            href={`mailto:${DATA_PROTECTION.contactEmail}?subject=${encodeURIComponent(DATA_PROTECTION.subjectLine)}`}
            className="underline underline-offset-2"
          >
            {DATA_PROTECTION.contactEmail}
          </a>{" "}
          or use the{" "}
          <Link href="/contact" className="underline underline-offset-2">
            contact page
          </Link>
          . We will respond within {DATA_PROTECTION.responseDays} days.
        </p>
        <p className="text-xs text-subtle">
          These requests are handled by a person reading that inbox, not yet by a self-service
          button — so the {DATA_PROTECTION.responseDays}-day commitment above depends on somebody
          owning it. Self-service export and deletion are planned.
        </p>
      </Clause>

      <Clause heading="How long we keep it">
        <Points
          items={RETENTION.map((rule) => (
            <span key={rule.what}>
              <strong>{rule.what}</strong> — {rule.period}. {rule.why}
            </span>
          ))}
        />
        <p>
          You do not have to wait for these periods to expire. You can ask us to delete your account
          and documents at any time, and we will.
        </p>
      </Clause>

      <Clause heading="Changes to this policy">
        <p>
          We record the version of this policy you accepted and the date you accepted it. If we
          change it in a way that affects your rights, we will tell you and ask you to accept the
          new version.
        </p>
      </Clause>
    </LegalDocument>
  );
}
