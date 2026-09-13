"use client";

/**
 * Staff: prices.
 *
 * There is one number on this page that decides what a student's bank alert
 * says, and it is the same number every page of the site quotes. That used to be
 * four separate values that were free to disagree — and did: the environment
 * charged ₦50,000 while the checkout button said ₦5,000.
 *
 * So the screen is built to make the consequence visible. Changing the fee shows
 * you a preview of the charge and a warning that the copy moves with it, and the
 * save is a separate, deliberate action.
 *
 * The cost estimates below are the other half: figures a student budgets
 * against. Each one shows what a reader currently sees, which is "ask us"
 * whenever nobody has verified it recently — the honest state, and the one that
 * happens by itself.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { Alert, Button, Field, LoadingRegion, Skeleton } from "@/components/ui";
import {
  type AdminCostEstimate,
  type AdminPricing,
  createCostEstimate,
  deleteCostEstimate,
  getAdminPricing,
  listCostEstimates,
  saveAdminPricing,
  saveCostEstimate,
} from "@/lib/pricing-admin";

const inputStyle =
  "w-full rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-subtle";

export default function PricingPage() {
  const [pricing, setPricing] = useState<AdminPricing | null>(null);
  const [baseline, setBaseline] = useState<AdminPricing | null>(null);
  const [estimates, setEstimates] = useState<AdminCostEstimate[]>([]);
  const [ready, setReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [readOnly, setReadOnly] = useState(false);

  const load = useCallback(async () => {
    const [loaded, rows] = await Promise.all([
      getAdminPricing(),
      listCostEstimates().catch(() => [] as AdminCostEstimate[]),
    ]);
    setPricing(loaded);
    setBaseline(loaded);
    setEstimates(rows);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await load();
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof ApiError && err.status === 403
            ? "Your account cannot see pricing. It sits with whoever manages payment configuration."
            : "We couldn't load pricing. Please refresh.",
        );
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  function update<K extends keyof AdminPricing>(key: K, value: AdminPricing[K]) {
    setPricing((current) => (current ? { ...current, [key]: value } : current));
    setNotice("");
  }

  const feeChanged =
    pricing && baseline && pricing.access_fee_amount !== baseline.access_fee_amount;
  const dirty = pricing && baseline && JSON.stringify(pricing) !== JSON.stringify(baseline);

  async function save() {
    if (!pricing || !baseline) return;
    setSaving(true);
    setError("");
    try {
      const patch: Partial<AdminPricing> = {};
      for (const key of Object.keys(pricing) as (keyof AdminPricing)[]) {
        if (pricing[key] !== baseline[key]) {
          (patch as Record<string, unknown>)[key] = pricing[key];
        }
      }
      const saved = await saveAdminPricing(patch);
      setPricing(saved);
      setBaseline(saved);
      setNotice(
        `Saved. Every page now quotes ${saved.formatted_access_fee}, and that is what the gateway charges.`,
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setReadOnly(true);
        setError(
          "You can read pricing but not change it — that needs payment configuration access.",
        );
      } else if (err instanceof ApiError) {
        setError(
          Object.entries(err.fieldErrors)
            .map(([field, messages]) => `${field}: ${messages.join(" ")}`)
            .join(" · ") || err.message,
        );
      } else {
        setError("We couldn't save that. Try again.");
      }
    } finally {
      setSaving(false);
    }
  }

  if (!ready) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-8">
        <LoadingRegion label="Loading pricing">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="mt-5 h-72" />
        </LoadingRegion>
      </div>
    );
  }

  if (!pricing) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <Alert tone="error">{error || "Pricing could not be loaded."}</Alert>
      </div>
    );
  }

  const staleCount = estimates.filter((row) => row.is_stale && row.is_active).length;

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="text-xl font-semibold text-ink">Prices</h1>
      <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted">
        One number, read by the payment gateway and by every page that quotes a price. There is no
        second place to update — that is the point.
      </p>

      {error ? (
        <div className="mt-5">
          <Alert tone="error">{error}</Alert>
        </div>
      ) : null}
      {notice ? (
        <div className="mt-5">
          <Alert tone="success">{notice}</Alert>
        </div>
      ) : null}

      {/* --- The access fee ------------------------------------------------ */}
      <section
        aria-labelledby="access-fee"
        className="mt-7 rounded-xl border border-line bg-surface p-5"
      >
        <h2 id="access-fee" className="font-display text-base font-bold text-ink">
          Platform access fee
        </h2>
        <p className="mt-1.5 text-sm leading-relaxed text-muted">
          Charged once, when a student activates their account.
        </p>

        <div className="mt-5 space-y-5">
          <div className="flex flex-wrap items-end gap-4">
            <Field label="Amount" htmlFor="fee-amount">
              <input
                id="fee-amount"
                type="text"
                inputMode="decimal"
                value={pricing.access_fee_amount}
                onChange={(event) => update("access_fee_amount", event.target.value)}
                className="w-40 rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink tabular-nums"
              />
            </Field>
            <Field label="Currency" htmlFor="fee-currency" hint="Three letters, e.g. NGN.">
              <input
                id="fee-currency"
                value={pricing.access_fee_currency}
                onChange={(event) =>
                  update("access_fee_currency", event.target.value.toUpperCase())
                }
                maxLength={3}
                className="w-24 rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink uppercase"
              />
            </Field>
            <p className="text-sm text-subtle">
              Currently charged:{" "}
              <span className="font-semibold text-ink">{baseline?.formatted_access_fee}</span>
            </p>
          </div>

          {feeChanged ? (
            <div className="rounded-lg border border-warning-line bg-warning-bg px-4 py-3">
              <h3 className="text-sm font-semibold text-ink">This changes what students pay</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink">
                Saving will charge <strong>{pricing.access_fee_amount}</strong>{" "}
                {pricing.access_fee_currency} on the next checkout, and the landing page, the terms,
                the refund policy and the share card will all say so immediately. Payments already
                completed are unaffected.
              </p>
            </div>
          ) : null}

          <Field
            label="One-line note"
            htmlFor="fee-note"
            hint="Shown next to the price on the fee section."
          >
            <input
              id="fee-note"
              value={pricing.access_fee_note}
              onChange={(event) => update("access_fee_note", event.target.value)}
              maxLength={200}
              className={inputStyle}
            />
          </Field>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button type="button" onClick={save} disabled={saving || !dirty || readOnly}>
            {saving ? "Saving…" : "Save price"}
          </Button>
          <span aria-live="polite" className="text-xs text-subtle">
            {dirty
              ? "Unsaved changes"
              : `Last changed ${new Date(pricing.updated_at).toLocaleString("en-NG")}`}
          </span>
        </div>
      </section>

      {/* --- Student costs ------------------------------------------------- */}
      <section
        aria-labelledby="student-costs"
        className="mt-6 rounded-xl border border-line bg-surface p-5"
      >
        <h2 id="student-costs" className="font-display text-base font-bold text-ink">
          What students still pay for
        </h2>
        <p className="mt-1.5 text-sm leading-relaxed text-muted">
          Not our money — proof of funds, embassy charges, flights. A figure nobody has checked
          inside {pricing.estimate_stale_after_days} days stops showing and says &ldquo;ask
          us&rdquo; instead. That happens by itself, which is the point: a stale number is worse
          than none, because a student budgets against it.
        </p>

        {staleCount ? (
          <p className="mt-3 rounded-lg border border-warning-line bg-warning-bg px-3 py-2.5 text-sm text-ink">
            {staleCount} of these {staleCount === 1 ? "is" : "are"} showing &ldquo;ask us&rdquo;.
            Each one is a question a student is asking that the page could answer.
          </p>
        ) : null}

        <div className="mt-5 space-y-4">
          {estimates.map((estimate) => (
            <EstimateRow key={estimate.id} estimate={estimate} onSaved={load} />
          ))}
          {estimates.length === 0 ? (
            <p className="text-sm text-muted">
              No cost rows yet. Run <code className="font-mono">make pricing-seed</code> to create
              the four the landing page expects.
            </p>
          ) : null}
        </div>

        <div className="mt-5 border-t border-line pt-4">
          <NewEstimate onSaved={load} />
        </div>
      </section>

      <p className="mt-6 text-xs text-subtle">
        <Link href="/staff/blog/settings" className="text-accent underline underline-offset-2">
          Blog settings
        </Link>{" "}
        control how pages look. This page controls what they cost.
      </p>
    </div>
  );
}

function EstimateRow({
  estimate,
  onSaved,
}: {
  estimate: AdminCostEstimate;
  onSaved: () => Promise<void>;
}) {
  const [draft, setDraft] = useState(estimate);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dirty = JSON.stringify(draft) !== JSON.stringify(estimate);
  const prefix = `estimate-${estimate.id}`;

  function update<K extends keyof AdminCostEstimate>(key: K, value: AdminCostEstimate[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function save() {
    setBusy(true);
    setError("");
    try {
      await saveCostEstimate(estimate.id, {
        label: draft.label,
        amount_display: draft.amount_display,
        note: draft.note,
        verified_on: draft.verified_on || null,
        verified_source: draft.verified_source,
        display_order: draft.display_order,
        is_active: draft.is_active,
      });
      await onSaved();
    } catch {
      setError("That did not save.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await deleteCostEstimate(estimate.id);
      await onSaved();
    } catch {
      setError("Could not remove that row.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-line bg-sunken p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-semibold text-ink">{estimate.label}</p>
        <p className="text-xs">
          <span className="text-subtle">Students see: </span>
          <span className={estimate.is_stale ? "font-semibold text-warning" : "font-mono text-ink"}>
            {estimate.public_amount}
          </span>
        </p>
      </div>

      {error ? (
        <p role="alert" className="mt-2 text-xs text-danger">
          {error}
        </p>
      ) : null}

      <div className="mt-3 grid gap-4 sm:grid-cols-2">
        <Field label="Label" htmlFor={`${prefix}-label`}>
          <input
            id={`${prefix}-label`}
            value={draft.label}
            onChange={(event) => update("label", event.target.value)}
            maxLength={120}
            className={inputStyle}
          />
        </Field>
        <Field
          label="Figure or range"
          htmlFor={`${prefix}-amount`}
          hint="As you would say it out loud. Blank shows “ask us”."
        >
          <input
            id={`${prefix}-amount`}
            value={draft.amount_display}
            onChange={(event) => update("amount_display", event.target.value)}
            placeholder="₦2.5m to ₦4m, held for six months"
            maxLength={120}
            className={inputStyle}
          />
        </Field>
        <Field label="Note" htmlFor={`${prefix}-note`} hint="Why it exists, or who it is paid to.">
          <input
            id={`${prefix}-note`}
            value={draft.note}
            onChange={(event) => update("note", event.target.value)}
            maxLength={240}
            className={inputStyle}
          />
        </Field>
        <Field
          label="Verified on"
          htmlFor={`${prefix}-verified`}
          hint="The day someone checked it. Blank or old means the figure is hidden."
        >
          <input
            id={`${prefix}-verified`}
            type="date"
            value={draft.verified_on ?? ""}
            onChange={(event) => update("verified_on", event.target.value || null)}
            className={inputStyle}
          />
        </Field>
        <Field
          label="Where the figure came from"
          htmlFor={`${prefix}-source`}
          hint="Internal only — never shown to a student."
        >
          <input
            id={`${prefix}-source`}
            value={draft.verified_source}
            onChange={(event) => update("verified_source", event.target.value)}
            maxLength={240}
            className={inputStyle}
          />
        </Field>
        <div className="flex items-start gap-2 pt-6">
          <input
            id={`${prefix}-active`}
            type="checkbox"
            checked={draft.is_active}
            onChange={(event) => update("is_active", event.target.checked)}
            className="mt-1"
          />
          <label htmlFor={`${prefix}-active`} className="text-sm text-ink">
            Show on the site
          </label>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button type="button" onClick={save} disabled={busy || !dirty}>
          {busy ? "Saving…" : "Save"}
        </Button>
        <button
          type="button"
          onClick={remove}
          disabled={busy}
          className="text-xs text-danger hover:underline"
        >
          Remove
        </button>
      </div>
    </div>
  );
}

function NewEstimate({ onSaved }: { onSaved: () => Promise<void> }) {
  const [label, setLabel] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  async function add() {
    setBusy(true);
    try {
      // Deliberately created with no figure: a row starts life as "ask us" and
      // becomes a number only once somebody has checked one.
      await createCostEstimate({ label: label.trim(), note: note.trim(), display_order: 100 });
      setLabel("");
      setNote("");
      await onSaved();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2.5">
      <label htmlFor="new-estimate-label" className="block text-xs font-semibold text-muted">
        Add a cost
      </label>
      <input
        id="new-estimate-label"
        value={label}
        onChange={(event) => setLabel(event.target.value)}
        placeholder="Credential evaluation"
        maxLength={120}
        className={inputStyle}
      />
      <label htmlFor="new-estimate-note" className="block text-xs font-semibold text-muted">
        Note
      </label>
      <input
        id="new-estimate-note"
        value={note}
        onChange={(event) => setNote(event.target.value)}
        placeholder="Paid to the evaluating body, not to us."
        maxLength={240}
        className={inputStyle}
      />
      <Button
        type="button"
        variant="secondary"
        onClick={add}
        disabled={busy || label.trim().length < 3 || note.trim().length < 5}
      >
        {busy ? "Adding…" : "Add"}
      </Button>
    </div>
  );
}
