import Link from "next/link";
import { Clause, LegalDocument, Points } from "@/components/legal";
import { ACCESS_FEE, REFUND } from "@/lib/company";

export const metadata = {
  title: "Refund policy — Nasuru",
  description: `When the ${ACCESS_FEE.formatted} access fee is refundable, when it is not, and how to ask.`,
};

export default function RefundPolicyPage() {
  return (
    <LegalDocument
      title="Refund policy"
      updated="10 September 2026"
      summary={`The access fee is ${ACCESS_FEE.formatted}, paid once. This page says when we give it back. We link to it from the home page before you pay, because a refund policy you only find afterwards is not a policy.`}
    >
      <Clause heading={`Changed your mind: ${REFUND.coolingOffDays} days`}>
        <p>
          You can ask for a <strong>full refund within {REFUND.coolingOffDays} days</strong> of
          paying, for any reason at all, as long as our team has not yet reviewed one of your
          documents.
        </p>
        <p>
          Once a reviewer has checked a document, the work you paid for has been done and this
          window closes. You will always know when that has happened, because a review changes the
          status on your checklist and we email you.
        </p>
        <p>
          No explanation is required and we will not try to talk you out of it. If you want to check
          before uploading anything, your checklist page shows the status of every document.
        </p>
      </Clause>

      <Clause heading="When we refund in full, whatever the date">
        <Points
          items={[
            <>
              <strong>You were charged twice.</strong> Duplicate payments are refunded in full, and
              we will find them ourselves during nightly reconciliation even if you do not ask.
            </>,
            <>
              <strong>You paid but never got access.</strong> If a payment succeeded at the gateway
              and your account was not unlocked, we will either unlock it or refund you — your
              choice.
            </>,
            <>
              <strong>We cannot serve you.</strong> If no school we support matches what you are
              applying for, we refund in full.
            </>,
          ]}
        />
      </Clause>

      <Clause heading="When we do not refund">
        <Points
          items={[
            <>
              <strong>A school rejected your application.</strong> The fee pays for preparing and
              tracking a complete application, which is work we did. Admission is the school&apos;s
              decision, and we say so before you pay.
            </>,
            <>
              <strong>An embassy refused your visa.</strong> Same reasoning.
            </>,
            <>
              <strong>Documents were found to be forged.</strong> Accounts closed for document fraud
              are closed without refund.
            </>,
          ]}
        />
      </Clause>

      <Clause heading="How to ask for a refund">
        <p>
          Write to us through the{" "}
          <Link href="/contact" className="underline underline-offset-2">
            contact page
          </Link>{" "}
          with the email address on your account and the payment reference. We will acknowledge
          within {REFUND.acknowledgeWorkingDays} working days and tell you the outcome, with a
          reason, within {REFUND.decideWorkingDays}.
        </p>
        <p>
          Approved refunds go back to the account that paid, through the same payment provider.
          Their processing time is outside our control and is usually {REFUND.gatewayWorkingDays}{" "}
          working days.
        </p>
      </Clause>
    </LegalDocument>
  );
}
