import Link from "next/link";
import { Clause, DraftClause, LegalDocument, NeedsSignOff, Points } from "@/components/legal";
import { COMPANY, REFUND, formattedAddress } from "@/lib/company";
import { getPricing, isPriceKnown } from "@/lib/pricing";

export const metadata = {
  title: "Terms of service — Nasuru",
  description: "What Nasuru does for you, what it does not, and what each side is responsible for.",
};

export default async function TermsPage() {
  // The fee is a database row, not a constant — see @/lib/pricing. When it is
  // unreachable the clause says "a one-off access fee" rather than inventing a
  // number, because a wrong figure in the terms is a contract problem.
  const pricing = await getPricing();
  const feeText = isPriceKnown(pricing) ? pricing.access_fee.formatted : "a one-off access fee";

  return (
    <LegalDocument
      title="Terms of service"
      updated="10 September 2026"
      summary="Nasuru helps you assemble and track a complete university application. We do not decide admissions and we do not decide visas. This page sets out what we owe you and what we need from you."
    >
      <Clause heading="What we provide">
        <Points
          items={[
            "A document checklist built from the published requirements of the schools you choose.",
            "Review of each document you upload, with written feedback if something needs redoing.",
            "Tracking of your applications across every school on your list.",
            "A counsellor you can message inside the platform.",
          ]}
        />
      </Clause>

      <Clause heading="What we do not provide">
        <p>This matters more than anything else on this page, so it is stated plainly:</p>
        <Points
          items={[
            <>
              <strong>We do not decide admissions.</strong> Schools do. A complete, verified
              checklist improves your chances; it does not guarantee an offer.
            </>,
            <>
              <strong>We do not decide visas.</strong> Embassies do. No part of our fee is
              contingent on, or a promise of, a visa outcome.
            </>,
            <>
              <strong>We do not pay third-party fees.</strong> School application fees, English test
              fees, and visa fees are paid by you, directly to those bodies.
            </>,
          ]}
        />
        <p>
          Anyone telling you that an agency can guarantee admission or a visa is misleading you.
          That includes us.
        </p>
      </Clause>

      <Clause heading="The access fee">
        <p>
          Access to the platform costs {feeText}, paid once. The fee is stated on our home page
          before you create an account, and it is the only charge we make for the service described
          above.
        </p>
        <p>
          Payment is confirmed by our payment provider, not by your browser reaching a success page.
          If a payment is taken but your account is not unlocked, contact us and we will reconcile
          it against the gateway record.
        </p>
        <p>
          You can change your mind: a full refund is available within {REFUND.coolingOffDays} days
          of paying, provided we have not yet reviewed one of your documents. The{" "}
          <Link href="/refund-policy" className="underline underline-offset-2">
            refund policy
          </Link>{" "}
          sets out every case in full.
        </p>
      </Clause>

      <Clause heading="What we need from you">
        <Points
          items={[
            "Documents that are genuine and belong to you.",
            "Information that is accurate and kept up to date.",
            "Your own account — do not share your sign-in with anyone else.",
          ]}
        />
        <p>
          We will close, without refund, any account we find submitting forged or altered documents.
          Document fraud puts every other student the agency represents at risk with the same
          schools.
        </p>
      </Clause>

      <Clause heading="Referrals">
        <p>
          A referral reward is earned when the person you referred makes a confirmed payment — not
          when they sign up. The reward terms that applied on the day it was earned are the terms we
          honour, even if the programme changes afterwards.
        </p>
        <p>
          Rewards for self-referrals, duplicate accounts, or payments that are later reversed are
          withdrawn.
        </p>
        <p>
          A reward becomes withdrawable once the payment that earned it is past its{" "}
          {REFUND.coolingOffDays}-day refund window. That follows from the refund policy rather than
          being a separate rule: a reward cannot be paid out on money that may still be returned.
        </p>
        <NeedsSignOff>
          Two payout mechanics remain open and must be set before referral withdrawals are enabled:
          the minimum balance before a payout can be requested, and what happens to a balance that
          is never claimed.
        </NeedsSignOff>
      </Clause>

      <Clause heading="Ending your account">
        <p>
          You can ask us to close your account at any time through the{" "}
          <Link href="/contact" className="underline underline-offset-2">
            contact page
          </Link>
          . We may suspend an account that breaches these terms, and will tell you why.
        </p>
      </Clause>

      <Clause heading="Liability, governing law and disputes">
        <DraftClause>
          <p>
            <strong>What we are responsible for.</strong> We are responsible for providing the
            service described in these terms with reasonable care and skill. Where we fail to do
            that and you lose money as a direct result, our total liability to you is limited to the
            fees you have paid us in the twelve months before the claim.
          </p>
          <p>
            <strong>What we are not responsible for.</strong> We are not liable for the decisions of
            schools or embassies, for fees you pay directly to third parties, or for indirect or
            consequential loss — including lost opportunity, lost earnings, or the cost of a
            deferred academic year.
          </p>
          <p>
            <strong>What cannot be limited.</strong> Nothing in these terms excludes liability for
            fraud, for death or personal injury caused by our negligence, or for anything else that
            Nigerian law does not allow to be excluded.
          </p>
          <p>
            <strong>Governing law.</strong> These terms are governed by the laws of the Federal
            Republic of Nigeria, and the courts of Lagos State have exclusive jurisdiction.
          </p>
          <p>
            <strong>Before going to court.</strong> Tell us first. Most disputes are a
            misunderstanding about what was promised, and we would rather fix it than argue about
            it. If we cannot resolve it between us within 30 days, either side may go to court.
          </p>
        </DraftClause>
        <p className="text-xs text-subtle">
          The wording above is conventional for a service of this kind and is written to be
          intelligible rather than defensive, but it has not yet been reviewed by a
          Nigerian-qualified lawyer. It should be, before launch.
        </p>
      </Clause>

      <Clause heading="Who you are contracting with">
        <p>
          {COMPANY.legalName}, registered in Nigeria, company registration number{" "}
          <span className="font-mono">{COMPANY.registrationNumber}</span>, at {formattedAddress()}.
        </p>
      </Clause>
    </LegalDocument>
  );
}
