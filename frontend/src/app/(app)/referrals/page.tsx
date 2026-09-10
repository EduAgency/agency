"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { authFetch } from "@/lib/auth/client";
import { useSession } from "@/lib/auth/SessionProvider";
import { Alert, BackLink, Button, Field, inputClass, StatusBadge } from "@/components/ui";
import type { ReferralSummary } from "@/types";

interface ReferralEvent {
  id: string;
  event_type: string;
  student_name: string;
  is_flagged: boolean;
  created_at: string;
}

interface ReferralReward {
  id: string;
  amount: string;
  currency: string;
  status: string;
  trigger: string;
  created_at: string;
}

interface ReferralData {
  summary: ReferralSummary & { total_paid_out: string };
  events: ReferralEvent[];
  rewards: ReferralReward[];
  payouts: { id: string; amount: string; status: string; requested_at: string }[];
}

export default function ReferralsPage() {
  const router = useRouter();
  const { session, loading, hasAccess } = useSession();
  const [data, setData] = useState<ReferralData | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const [showPayout, setShowPayout] = useState(false);

  const load = useCallback(() => {
    authFetch<ReferralData>("/api/referrals/mine/")
      .then(setData)
      .catch(() => setError("We couldn't load your referral details."));
  }, []);

  useEffect(() => {
    if (loading) return;
    if (!session) return router.replace("/login");
    if (!hasAccess) return router.replace("/checkout");
    load();
  }, [loading, session, hasAccess, router, load]);

  async function copy() {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(data.summary.share_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Couldn't copy automatically — select the link and copy it.");
    }
  }

  if (loading || !data) return <div className="p-12 text-sm text-subtle">Loading…</div>;

  const balance = Number(data.summary.available_balance);

  return (
    <div className="mx-auto max-w-2xl px-6 py-12">
      <BackLink href="/dashboard">Back to my applications</BackLink>
      <h1 className="mt-4 text-2xl font-semibold text-ink">Refer a friend</h1>
      <p className="mt-1 text-sm text-muted">
        Share your link. You earn when someone you referred activates their account — not just when
        they sign up.
      </p>

      {error && (
        <div className="mt-6">
          <Alert>{error}</Alert>
        </div>
      )}

      <section className="mt-8 rounded-xl border border-line p-5">
        <p className="text-xs font-medium tracking-wide text-subtle uppercase">Your link</p>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <code className="min-w-0 flex-1 truncate rounded bg-sunken px-3 py-2 text-sm">
            {data.summary.share_url}
          </code>
          <Button variant="secondary" onClick={copy}>
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
        <p className="mt-2 text-xs text-subtle">
          Code: <span className="font-mono">{data.summary.code}</span>
        </p>
      </section>

      <section className="mt-6 grid grid-cols-3 gap-3">
        {[
          { label: "Signed up", value: data.summary.signups },
          { label: "Activated", value: data.summary.conversions },
          { label: "Earned", value: `₦${Number(data.summary.total_earned).toLocaleString()}` },
        ].map((stat) => (
          <div key={stat.label} className="rounded-xl border border-line p-4">
            <p className="text-xs text-subtle">{stat.label}</p>
            <p className="mt-1 text-xl font-semibold text-ink tabular-nums">{stat.value}</p>
          </div>
        ))}
      </section>

      <section className="mt-6 rounded-xl border border-line p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm text-muted">Available to withdraw</p>
            <p className="text-2xl font-semibold text-ink">₦{balance.toLocaleString()}</p>
          </div>
          <Button onClick={() => setShowPayout(true)} disabled={balance <= 0}>
            Request payout
          </Button>
        </div>
        {balance <= 0 && (
          <p className="mt-2 text-xs text-subtle">
            Rewards become available once the referred student&apos;s payment is confirmed and the
            reward is approved.
          </p>
        )}
      </section>

      {showPayout && (
        <PayoutForm
          onDone={() => {
            setShowPayout(false);
            load();
          }}
          onCancel={() => setShowPayout(false)}
        />
      )}

      {data.rewards.length > 0 && (
        <section className="mt-8">
          <h2 className="text-base font-semibold text-ink">Your rewards</h2>
          <ul className="mt-3 divide-y divide-line rounded-xl border border-line">
            {data.rewards.map((reward) => (
              <li key={reward.id} className="flex items-center justify-between p-4 text-sm">
                <div>
                  <p className="font-medium text-ink">₦{Number(reward.amount).toLocaleString()}</p>
                  <p className="text-xs text-subtle">
                    {new Date(reward.created_at).toLocaleDateString()}
                  </p>
                </div>
                <StatusBadge
                  status={
                    reward.status === "paid"
                      ? "verified"
                      : reward.status === "void"
                        ? "rejected"
                        : "pending_review"
                  }
                  label={
                    { pending: "Under review", approved: "Approved", paid: "Paid", void: "Void" }[
                      reward.status
                    ] ?? reward.status
                  }
                />
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.events.length > 0 && (
        <section className="mt-8">
          <h2 className="text-base font-semibold text-ink">Activity</h2>
          <ul className="mt-3 space-y-2 text-sm text-muted">
            {data.events.map((event) => (
              <li key={event.id} className="flex justify-between gap-4">
                <span>
                  {event.student_name}{" "}
                  {{
                    signup: "signed up",
                    paid: "activated their account",
                    offer: "received an offer",
                    enrolled: "enrolled",
                  }[event.event_type] ?? event.event_type}
                </span>
                <span className="shrink-0 text-xs text-subtle">
                  {new Date(event.created_at).toLocaleDateString()}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function PayoutForm({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [form, setForm] = useState({ bank_name: "", account_number: "", account_name: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await authFetch("/api/referrals/payout/", { method: "POST", body: form });
      onDone();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? (Object.values(err.fieldErrors)[0]?.[0] ?? err.message)
          : "We couldn't submit that request.",
      );
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-4 space-y-4 rounded-xl border border-line p-5">
      <h2 className="text-base font-semibold text-ink">Payout details</h2>
      {error && <Alert>{error}</Alert>}

      <Field label="Bank" htmlFor="bank_name">
        <input
          id="bank_name"
          required
          value={form.bank_name}
          onChange={(e) => setForm({ ...form, bank_name: e.target.value })}
          className={inputClass}
        />
      </Field>
      <Field label="Account number" htmlFor="account_number" hint="10 digits.">
        <input
          id="account_number"
          required
          inputMode="numeric"
          pattern="\d{10}"
          value={form.account_number}
          onChange={(e) => setForm({ ...form, account_number: e.target.value })}
          className={inputClass}
        />
      </Field>
      <Field label="Account name" htmlFor="account_name">
        <input
          id="account_name"
          required
          value={form.account_name}
          onChange={(e) => setForm({ ...form, account_name: e.target.value })}
          className={inputClass}
        />
      </Field>

      <div className="flex gap-3">
        <Button type="submit" disabled={busy}>
          {busy ? "Submitting…" : "Request payout"}
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
