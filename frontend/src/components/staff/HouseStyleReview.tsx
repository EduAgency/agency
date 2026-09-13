"use client";

/**
 * The house-style scan, shown to the writer.
 *
 * The same scan gates publishing server-side (apps/blog/services.check_publishable),
 * so this is not advice — it is the list of things that will stop the post going
 * live. Showing it while the draft is still open is the difference between
 * fixing three sentences now and arguing with a 400 response later.
 *
 * Each flag quotes the text it matched. A rule that says "unverified figure" and
 * makes the writer hunt for it gets ignored; one that quotes the sentence gets
 * fixed.
 */

import { HOUSE_STYLE_FLAG_LABELS, type HouseStyleReview as Review } from "@/lib/blog-admin";

export function HouseStyleReview({ review, label }: { review: Review; label?: string }) {
  if (review.ok) {
    return (
      <p className="flex items-start gap-2 rounded-lg border border-success-line bg-success-bg px-3 py-2.5 text-sm text-ink">
        <span aria-hidden="true" className="text-success">
          ✓
        </span>
        <span>{label ?? "Nothing here breaks the house style."}</span>
      </p>
    );
  }

  const byKind = new Map<string, Review["flags"]>();
  for (const flag of review.flags) {
    byKind.set(flag.kind, [...(byKind.get(flag.kind) ?? []), flag]);
  }

  return (
    <div className="rounded-lg border border-warning-line bg-warning-bg px-3 py-3">
      <h4 className="text-sm font-semibold text-ink">
        {review.flags.length} {review.flags.length === 1 ? "thing" : "things"} to fix before this
        can be published
      </h4>
      <div className="mt-3 space-y-3">
        {[...byKind.entries()].map(([kind, flags]) => (
          <section key={kind}>
            <h5 className="text-xs font-semibold tracking-wide text-muted uppercase">
              {HOUSE_STYLE_FLAG_LABELS[kind as keyof typeof HOUSE_STYLE_FLAG_LABELS] ?? kind}
            </h5>
            <ul className="mt-1.5 space-y-2">
              {flags.map((flag, index) => (
                <li key={`${kind}-${index}`} className="text-sm leading-relaxed text-ink">
                  <p>{flag.why}</p>
                  <p className="mt-1 border-l-2 border-warning pl-2.5 text-muted italic">
                    …{flag.excerpt}…
                  </p>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
