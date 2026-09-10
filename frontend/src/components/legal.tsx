/**
 * Typographic shell shared by the four public policy documents, so privacy,
 * terms, refunds and contact read as one set rather than four separate pages.
 */

export function LegalDocument({
  title,
  updated,
  summary,
  children,
}: {
  title: string;
  updated: string;
  summary: string;
  children: React.ReactNode;
}) {
  return (
    <article>
      <h1 className="text-3xl font-semibold text-ink">{title}</h1>
      <p className="mt-2 font-mono text-xs text-subtle">Last updated {updated}</p>
      <p className="mt-6 border-l-2 border-field-line pl-4 text-base text-muted">{summary}</p>
      <div className="mt-10 space-y-8">{children}</div>
    </article>
  );
}

export function Clause({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold text-ink">{heading}</h2>
      <div className="space-y-3 text-sm leading-relaxed text-muted">{children}</div>
    </section>
  );
}

/** Bulleted list in the same voice as the surrounding clause text. */
export function Points({ items }: { items: React.ReactNode[] }) {
  return (
    <ul className="space-y-2 pl-5">
      {items.map((item, index) => (
        <li key={index} className="list-disc marker:text-subtle">
          {item}
        </li>
      ))}
    </ul>
  );
}

/**
 * Wording that has been drafted but not yet reviewed by a lawyer.
 *
 * Different from NeedsSignOff: this clause HAS content and would operate if
 * published. The marker is a standing instruction to get it reviewed, not an
 * admission that it is blank — and it renders visibly so nobody forgets.
 */
export function DraftClause({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-warning-line bg-warning-bg px-4 py-3">
      <p className="text-xs font-semibold tracking-wide text-warning uppercase">
        Draft — not yet reviewed by counsel
      </p>
      <div className="mt-2 space-y-3 text-sm leading-relaxed text-muted">{children}</div>
    </div>
  );
}

/**
 * Marks a clause whose wording is a commercial or legal decision the business
 * has not made yet.
 *
 * Visible on purpose. A policy that quietly invents terms nobody agreed to is
 * worse than one that admits what is still open — and these markers are a
 * launch checklist: none of them should survive to production.
 */
export function NeedsSignOff({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-lg border border-warning-line bg-warning-bg px-4 py-3 text-sm text-warning">
      <strong className="font-semibold">Needs sign-off before launch:</strong> {children}
    </p>
  );
}
