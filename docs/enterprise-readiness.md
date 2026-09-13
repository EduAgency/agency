# Enterprise readiness

**Reviewed at** `b14cd0e` on `main` · **Scope** `frontend/src` (26 files, 9 routes) and
`backend/apps` (8 apps, 83 endpoints) · **Date** 10 September 2026

Every finding below cites a file and line in this repository and was verified against the
source. WCAG references are to 2.2 Level AA except 2.3.3, which is AAA and included because
the fix is a three-line CSS block.

---

## The verdict

The four engines are sound. Versioned form schemas, snapshotted checklists,
webhook-verified payments, payment-gated referral rewards — that is the hard part and it is
done, with 87 tests covering the invariants specifically.

The gap is the surface. The student app has broken links, no accessibility layer, and the
agency's own staff still work out of Django admin.

Nobody evaluating this product will test checklist snapshot isolation. They will tab through
a form, hit a 404 on the privacy policy, and ask who has MFA.

| Band | Count | What it means |
|---|---|---|
| **Blocking** | 4 | Visible breakage reachable within three clicks of the landing page |
| **High** | 8 | WCAG 2.2 AA failures and resilience gaps |
| **Medium** | 6 | Systemic — cheap now, expensive at 40 screens |
| **Capability** | 7 | Absent from the product, not merely unpolished |

---

## Section A — Blocking defects

### A1 · Six linked routes return 404, including every legal page

The landing page footer and dashboard link to `/privacy`, `/terms`, `/refund-policy`,
`/contact`, `/documents` and `/forgot-password`. None exist under `src/app/`. There is no
`not-found.tsx` either, so each renders the stock Next.js 404.

**Why it matters** — the landing page's own argument is that this audience is wary of scams
and that hiding the fee costs trust. A dead privacy policy costs more. The footer
simultaneously asserts processing "in line with the Nigeria Data Protection Regulation"; an
unreachable policy makes that claim indefensible.

**Fix** — author the four legal/contact pages, build `/documents` as a cross-application
document library, add a branded `not-found.tsx`, and add a CI check that every internal
`href` resolves to a route.

### A2 · Password reset is throttled on the backend but has no front door

DRF declares a `password_reset` throttle scope at `5/hour` in `config/settings.py:206`. The
login page links to `/forgot-password`. That route does not exist.

**Why it matters** — a student who forgets their password after paying the ₦5,000 access fee
has no recovery path and becomes a support ticket. This is the highest-volume support driver
in any consumer product.

**Fix** — request-reset and confirm-reset screens against the existing endpoints, plus
resend-verification. The dashboard already nags for email verification with no way to re-send
the link.

### A3 · File validation errors are reported through `window.alert()`

`frontend/src/components/forms/FormRenderer.tsx:319` — when a passport scan exceeds the size
limit or has the wrong type, the app fires a native modal, clears the input and drops the
value.

**Why it matters** — a blocking OS dialog is unstyleable, untranslatable, destroys context on
mobile, and is dismissed before assistive tech can associate it with the control. The message
vanishes on dismissal, so the student cannot re-read what went wrong. Every other error path
in the codebase is handled properly; this one is the exception.

**Fix** — route file errors through the same per-field `role="alert"` element every other
field type already uses, and keep the message on screen until the input changes.

### A4 · Grouped choice fields have a label pointing at nothing

`FormRenderer.tsx:167` renders `<label htmlFor={field.key}>` for the group question. For
`radio`, `multiselect` and `checkbox_group`, the `common` props object carrying
`id={field.key}` is never spread onto any input — so the label references an element ID that
does not exist, and the options sit in a bare `<div>` with no `<fieldset>`, `<legend>` or
`role="radiogroup"`.

**Why it matters** — a screen reader user hears "Yes, radio button, 1 of 1" with no question
attached and no group position. On the intake form, where conditional branching means the
question text is the only thing distinguishing two adjacent Yes/No pairs, the form becomes
unanswerable non-visually. The same code path drops `aria-describedby`, so help text and
errors are silent too.

**Fix** — render grouped choices as `<fieldset>` + `<legend>`, wire `aria-describedby` and
`aria-invalid` onto the fieldset, give each option a unique `id`.

*WCAG 1.3.1, 4.1.2.*

---

## Section B — Accessibility conformance

Measured against WCAG 2.2 AA — the bar written into most enterprise procurement and into
Nigeria's Discrimination Against Persons with Disabilities (Prohibition) Act.

Across all 26 source files the app contains **zero** skip links, **zero** live regions,
**zero** `:focus-visible` declarations, **zero** `sr-only` text and **zero** reduced-motion
guards.

The good news: the form layer already gets `aria-invalid`, `aria-describedby` and
`role="alert"` right, so the pattern to extend is established rather than absent.

| # | Finding | Severity | WCAG |
|---|---|---|---|
| B1 | No skip link, no landmark structure | High | 2.4.1 |
| B2 | Focus styling inconsistent, never `:focus-visible` | High | 2.4.7, 2.4.11 |
| B3 | Failed submit scrolls but never moves focus | High | 3.3.1, 2.4.3 |
| B4 | Asynchronous outcomes are never announced | High | 4.1.3 |
| B5 | Motion is unconditional | High | 2.3.3 |
| B6 | Product renders in Arial; theme layer is dead | High | — |
| B7 | No error boundaries | High | — |
| B8 | Upload has no progress, retry or resume | High | — |
| B9 | Nothing enforces any of this | Medium | — |
| B10 | Colour and target sizes never verified | Medium | 1.4.3, 2.5.8 |

### B1 · No skip link and no landmark structure

`layout.tsx` renders `<body>` → `SessionProvider` → page. Each page hand-rolls its own
`<main>` and its own `<nav>`; there is no `<header>` banner, no skip target, and no
`aria-label` distinguishing the two navs on the dashboard.

**Fix** — an app shell with a visually-hidden-until-focused skip link, a labelled banner, and
one `<main id="content">`.

### B2 · Focus styling is inconsistent and never uses `:focus-visible`

Inputs set `outline-none` and substitute a `focus:ring-1`. Buttons, links, the checklist
upload triggers and the landing-page CTA declare no focus style at all and fall back to the
UA outline — a different shape, colour and offset on every element, and close to invisible on
a dark surface.

**Fix** — one global `:focus-visible` token (ring colour, width, offset) applied to every
interactive element, with a documented 3:1 contrast against both adjacent surfaces.

### B3 · Failed submit scrolls to the error but never moves focus

`FormRenderer.tsx:67` calls `scrollIntoView` on the first invalid field and returns. Keyboard
focus stays on the submit button; nothing is announced. Per field, `FormRenderer.tsx:189`
renders `errors[0]` only, discarding the rest.

**Fix** — an error summary at the top of the form (a focusable heading listing every failure
as an in-page link), move focus to it on failed submit, show all messages per field.

### B4 · Asynchronous outcomes are never announced

Eight routes gate on `if (loading) return <main>Loading…</main>`. When data arrives the whole
subtree is swapped with no `aria-live` region and no `aria-busy`. A document upload
succeeding, a checklist re-syncing, a payment verifying — all change silently.

**Fix** — one app-level polite live region plus a toast primitive; `aria-busy` on regions
being refreshed; skeletons that preserve layout instead of a text swap.

### B5 · Motion is unconditional

`behavior: "smooth"` at `FormRenderer.tsx:67`, and `transition` on every button, card and
progress bar, with no `prefers-reduced-motion` query anywhere in the codebase.

**Fix** — a global reduced-motion block, and read the preference in JS before choosing a
scroll behaviour.

### B6 · The entire product renders in Arial

`globals.css:25` sets `font-family: Arial, Helvetica, sans-serif` on `body`. Lines 11–12 map
`--font-sans` to `--font-geist-sans`, a variable never defined because the `next/font` loader
that would define it was removed from `layout.tsx`. Separately, `globals.css` defines a
`--background`/`--foreground` pair under a `prefers-color-scheme` query that the body's
Tailwind `bg-white dark:bg-slate-950` classes immediately override.

Two competing theme systems, one of which does nothing, and a typeface nobody chose. This is
leftover `create-next-app` boilerplate, and it is the difference a buyer notices in the first
two seconds.

**Fix** — delete the dead vars, load a real typeface pair through `next/font`, define one
token layer that both Tailwind and raw CSS read from.

### B7 · No error boundaries — one thrown render blanks the app

No `error.tsx`, `global-error.tsx`, `loading.tsx` or `not-found.tsx` exists anywhere under
`src/app/`. Sentry is wired on the backend (`settings.py:323`) but there is no browser-side
reporting, so front-end crashes are invisible.

**Fix** — route-segment error boundaries with a recovery action, plus `@sentry/nextjs` with
session replay on errors only.

### B8 · Document upload has no progress, no retry and no resume

`lib/applications.ts:30` posts a `FormData` through `fetch`. `fetch` cannot report upload
progress; on failure `ChecklistView` shows "That upload didn't go through. Try again." and
the student re-picks the file from scratch.

**Why it matters** — this is the product's central action, performed by students on Nigerian
mobile data, uploading multi-megabyte scans of passports and transcripts. A silent
progressless upload that can fail at 90% is the most likely single cause of funnel
abandonment.

**Fix** — `XMLHttpRequest` or presigned direct-to-S3 upload with a determinate progress bar,
automatic retry with backoff, client-side image compression, drag-and-drop and camera capture
on mobile.

### B9 · Nothing enforces any of this

`eslint.config.mjs` extends `core-web-vitals` and `typescript` only — no `jsx-a11y`.
`package.json` has no test script, no test runner and no dependencies beyond Next and React.
The backend has 87 tests; the frontend has none.

**Fix** — `eslint-plugin-jsx-a11y` at error level, Vitest + Testing Library for the form
engine's conditional logic, Playwright with `@axe-core/playwright` asserting zero violations
on every route, and a keyboard-only walkthrough of intake → upload → checkout in CI.

### B10 · Colour, contrast and target sizes are chosen per component, never verified

Every colour is an inline Tailwind literal with a hand-written `dark:` twin — `STATUS_STYLES`
in `ui/index.tsx` carries sixteen. Checkboxes and radios are `h-4 w-4` (16px). No documented
palette exists to check contrast against.

Credit where due: `ProgressBar` already pairs its colour with a numeric percentage and
`StatusBadge` always carries a text label — colour is never the sole signal, so WCAG 1.4.1
holds.

**Fix** — lift colour into semantic tokens (`--surface`, `--danger`, `--status-verified`…),
verify each pair at AA in both themes once, set a 24px minimum interactive target.

---

## Section C — Capability gaps

Not defects. Things the product does not have, each a line item on a standard enterprise
security questionnaire or an NDPR data-protection audit.

| Capability | Today | What is missing |
|---|---|---|
| **Staff workspace** | Django admin | The README calls Django admin "the agency's daily workspace". Reviewers verify passports, counsellors chase students and finance reconciles payments through generic CRUD screens. No review queue, no side-by-side document viewer, no bulk actions, no saved views, no keyboard shortcuts. The largest single gap between the product and its category. |
| **MFA** | None | Zero references to TOTP, OTP or two-factor across all eight backend apps. Staff accounts hold students' passports and national identity documents behind a password alone. |
| **SSO** | None | No SAML or OIDC. Blocks any partner institution or agency group requiring directory-managed accounts, and blocks SCIM deprovisioning when a counsellor leaves. |
| **Session control** | JWT only | 30-minute access tokens with rotation, mirrored to `localStorage` — a deliberate, documented trade-off in `lib/auth/store.ts`. But no active-device list, no remote revoke, no "sign out everywhere" after a lost phone. Procurement flags `localStorage` token storage by default; the answer needs to be httpOnly cookies or a written compensating-control statement. |
| **Notification prefs** | None | Email, SMS and WhatsApp templates exist with categories, and Celery Beat sends nudges — but no preference model, no per-channel opt-out, no unsubscribe, no quiet hours. Unsolicited SMS to Nigerian numbers with no opt-out is an NDPR exposure, not just an annoyance. |
| **In-app inbox** | Threads exist | `MessageThread` and `Message` models are built, and the landing page promises "a counsellor you can message inside the platform" — with no messaging UI on any of the nine routes. A promised feature with no surface. |
| **Data subject rights** | None | NDPR alignment is asserted publicly. NDPR grants access, rectification, portability and erasure. There is no export-my-data, no deletion request flow, no retention schedule and no soft-delete anywhere in the models — so an erasure request today means hand-written SQL against encrypted document records. |
| **Audit trail** | Solid | A single `record()` entry point in `apps/core/audit.py` with a redaction allowlist covering passwords, tokens, signatures and gateway keys, used across 23 files. Genuinely enterprise-grade already — it needs a staff-facing viewer and an export, not rework. |
| **Rate limiting** | Scoped | Signup, login, password reset and upload are throttled. The other ~79 endpoints are unlimited per user. |

---

## Section D — Perks that would earn their keep

Filtered hard. Each removes a support ticket, a drop-off, or a manual step for staff — the
three things that make software feel world-class rather than merely feature-rich.

- **D1 · Make the checklist the product, not a list.** Each item already carries a category, a
  status and a rejection reason. Add what happens next and when ("we review within 2 working
  days"), a worked example of an acceptable document, and one "what should I do today" prompt
  on the dashboard. The one thing an anxious applicant wants is to know they are not stuck.

- **D2 · Autosave and resumability.** `onSaveDraft` exists in `FormRenderer` but must be
  pressed. Debounced autosave with a visible "saved 12:04" stamp, restoration on return, and a
  warning before navigating away with unsaved answers.

- **D3 · A staff review queue with a document viewer.** One screen: oldest-waiting item, the
  document rendered beside the requirement it must satisfy, verify/reject with canned reasons
  plus free text, then advance. `J`/`K` to move, `V` to verify. This is where staff hours
  actually go.

- **D4 · Global search and a command palette.** Staff jump to a student, application, school or
  payment reference; students search their own documents. Nothing is currently findable except
  by navigation.

- **D5 · User-controlled appearance and locale.** An explicit light/dark/system toggle (today
  the OS decides, full stop), a text-size control, and locale-aware money and dates. The fee is
  hardcoded as "₦5,000" in the landing-page markup; formatting should run through `Intl`
  against the `Africa/Lagos` timezone the backend already declares.

- **D6 · Offline tolerance.** Detect connection loss, queue the upload, say plainly that it will
  resume. On this audience's network conditions that converts a failure into a delay.

---

## Roadmap

Four phases, sequenced by dependency rather than size. The order matters: the token and shell
work in Phase 2 is what makes Phases 3 and 4 cheap, and doing it after building forty more
screens costs several times more.

Gates are written as observable tests so that "done" is not a matter of opinion.

### Phase 1 — Stop the bleeding ✅ shipped

> **Gate:** no dead link, no native dialog, no unanswerable form. **Met** — all 13 internal
> links resolve, `npm run build` passes 19 routes, `tsc --noEmit` and `eslint` are clean.

Pure defect work on the existing surface. Nothing here was new product.

| Item | What shipped |
|---|---|
| **A1** | `/privacy`, `/terms`, `/refund-policy`, `/contact` under a shared `(legal)` layout; `/documents` document vault; branded `not-found.tsx` |
| **A2** | `/forgot-password`, `/reset-password`, `/verify-email`; resend-verification wired into the dashboard notice |
| **A3** | `window.alert` replaced with the same per-field `role="alert"` every other field type uses |
| **A4** | Grouped choices render as `fieldset`/`legend` with per-option `id`s and wired `aria-describedby` |
| **B3** | Error summary at the top of every form, focus moved to it on failed submit, all messages shown per field |
| **B5** | `prefers-reduced-motion` respected before any programmatic scroll |
| **B6** | Source Sans 3 + JetBrains Mono via `next/font`; dead `--font-geist-*` and duplicate theme vars removed |
| **B7** | `error.tsx`, `global-error.tsx`, and `lib/report-error.ts` as the single Sentry-ready choke point |

**B3 and B5 were pulled forward from Phase 2** — both live on the same lines of
`FormRenderer.tsx` as A3 and A4, so splitting them across phases would have meant rewriting
the same file twice.

**Two things surfaced during the work that were not in the original audit:**

1. **The "documents are stored encrypted" claim was not backed by configuration.** The landing
   page footer and the privacy policy both state it. `EncryptedTextField` covers *payment
   gateway credentials only*; documents go to S3 with a private ACL and 15-minute signed URLs,
   but no server-side encryption was requested. Fixed by adding
   `"object_parameters": {"ServerSideEncryption": "AES256"}` to the S3 `STORAGES` config — AWS
   encrypts by default since 2023, but S3-compatible providers may not, and a published claim
   should not rest on a provider default.

2. **Browser-side Sentry still needs a dependency and a DSN.** `lib/report-error.ts` is the
   single choke point every boundary reports through; wiring it is `npm install @sentry/nextjs`,
   a `NEXT_PUBLIC_SENTRY_DSN`, and replacing one `console.error`.

**The legal pages carried nine visible `Needs sign-off before launch` callouts. Seven are now
resolved** (see below); the two that remain are genuine open decisions.

### Phase 1b — Closing out the two flagged items ✅ shipped

**1. The encryption claim is now backed and guarded.** Beyond the `ServerSideEncryption: AES256`
setting, `backend/tests/test_storage_claims.py` asserts it — along with the private ACL, the
15-minute URL expiry, no-overwrite, and that gateway credentials use `EncryptedTextField`. The
claim now fails the build if someone removes the setting, rather than quietly becoming false.
`backend/.env.example` documents both the encryption requirement and a **data-residency
finding**: the default region is `eu-west-1` (Ireland), which the NDPR treats as an
international transfer requiring disclosure and a lawful basis. Choose `af-south-1` or a
Nigeria-resident provider to avoid the obligation.

**2. Seven of nine sign-off callouts resolved**, using decisions the business supplied:

| Clause | Resolution |
|---|---|
| Refund cooling-off | **Full refund within 14 days**, provided no document has been reviewed. Now stated on the landing page next to the fee, not just in the policy |
| Retention schedule | Documents 24 months after close · payment records 7 years · inactive accounts 24 months with two warning emails · audit logs 7 years |
| Company identity | RC 9759223, 19 Obashoro Street, Oke Odo, Alimosho, Lagos State |
| Support contact | support@nasuru.com · +234 812 934 1700 (call and WhatsApp) · Mon–Sat, 8am–5pm WAT |
| DPO contact | Routed to the support address with a required subject line — the NDPR wants a contact point, not a published personal name |
| Security disclosure | Published address plus a good-faith safe-harbour statement |
| Liability / governing law | **Drafted** under a visible `Draft — not yet reviewed by counsel` marker: Nigerian law, Lagos jurisdiction, liability capped at 12 months of fees, indirect loss excluded, non-excludable liabilities preserved, talk-to-us-first before court |

Everything above lives in one file, `frontend/src/lib/company.ts`, rather than scattered across
five pages, and the fee renders through `Intl.NumberFormat` instead of a hand-typed `₦5,000`.

**What deliberately remains open — two callouts and six PENDING values:**

- **Sub-processor disclosure.** Paystack, Flutterwave and Sentry are named because the codebase
  integrates them. Hosting, object storage and the email/SMS provider are deployment choices
  nobody has made, so they render as `PENDING`. Naming the wrong processor in a published
  policy is worse than an incomplete list.
- **Referral payout mechanics.** One rule was derivable and is now stated as policy: a reward
  becomes withdrawable only once the payment that earned it is past its 14-day refund window,
  since a reward cannot be paid on money that may still be returned. The minimum payout balance
  and the treatment of unclaimed balances are still open.

**These can no longer ship by accident.** `npm run check:launch` reports every remaining marker,
and **fails the build** under `NODE_ENV=production`, `VERCEL_ENV=production`, or `--strict`. It
is wired into `npm run verify`.

### Phase 2 — Build the foundation everything else sits on ✅ shipped

> **Gate:** axe reports zero violations on all routes; keyboard-only walkthrough passes.
> **Met** — 78 Playwright tests pass on desktop and mobile, including 44 axe scans (11 public
> routes × 2 colour schemes × 2 viewports) with zero violations. `npm run verify` is green.

| Item | What shipped |
|---|---|
| **B2, B10** | 27 semantic tokens in three theme states; one global `:focus-visible` ring; `npm run check:contrast` verifies **54 required pairs** across both themes and fails the build on a regression |
| **B1** | `AppShell` — skip link, banner, single `<main id="content">`, `aria-label`led navs, `aria-current` on the active item |
| **B4** | `AnnouncerProvider` — always-mounted polite and assertive live regions, plus a toast surface; `Skeleton` / `LoadingRegion` / `CardListSkeleton` replace the `Loading…` text swap |
| **B8** | `lib/upload.ts` — XHR progress, bounded retry with exponential backoff, cancellation, one token refresh mid-upload; checklist rows gained a progress bar, a cancel control and drag-and-drop |
| **B9** | `eslint-plugin-jsx-a11y` at **error** level, Vitest + Testing Library (10 tests), Playwright + axe (78 tests), `npm run verify` chaining all of it |

**How the token layer is enforced.** `scripts/check-contrast.mjs` parses `globals.css` rather
than duplicating its values, so it cannot drift from what it checks. It grades pairs at three
levels: `text` (4.5:1, WCAG 1.4.3), `ui` (3:1, WCAG 1.4.11 — input borders and the focus ring,
where the border is the only thing identifying the control), and `decor` (reported, not
enforced). That distinction matters: applying 3:1 to every decorative panel border would force
a heavy, garish UI in the name of a rule that does not apply to it. It also asserts the
`prefers-color-scheme` block and the `[data-theme="dark"]` block stay identical, so viewers on
the default "system" setting never get a different palette from those who chose dark.

**Three real defects the new tooling caught immediately:**

1. **Input borders failed WCAG 1.4.11.** `border-slate-300` on white is ~1.5:1 against a
   required 3:1 — every text input in the product. Fixed with a dedicated `--field-line` token
   (3.38:1 light, 3.75:1 dark) kept separate from the decorative `--line`.
2. **`jsx-a11y` failed the build on my own Phase 1 code** — `autoFocus` on the two new password
   screens. Removed rather than suppressed: autofocus skips the heading and explanatory text
   that give the field its context.
3. **The error summary was indistinguishable from field errors.** Both are `role="alert"`, so
   the summary had no accessible name. Fixed with `aria-labelledby` pointing at its own heading.

**Also cleaned up on the way through:** all 21 files carrying hand-written `dark:` variants
migrated to tokens (**zero `dark:` variants remain in `src/`**); nested `<main>` elements
removed from seven `(app)` routes now that the shell provides the landmark; the dashboard's
duplicate hand-rolled nav deleted; `@types/node` bumped from 20 to 22 (Vitest 5 and Vite 8 both
require it); Prettier added and the source formatted consistently.

**One caveat on e2e coverage.** The axe suite covers the 11 routes reachable without a backend.
Signed-in routes — dashboard, checklist, documents, referrals, checkout — are not yet scanned,
because there is no seeded test API to authenticate against. Their shared machinery (the form
engine, the shell, the upload flow) is covered by unit tests, but **the gate is weaker there
than it looks**. Standing up a seeded fixture API is the honest next step, and belongs with the
Phase 3 staff console work.

### Phase 3 — Give the agency a workspace 🟡 core shipped, three items outstanding

> **Gate:** a reviewer completes a full day without opening Django admin.
> **Not yet met** — document review, student lookup and search are covered, but payments,
> messaging and audit still send staff to Django admin. See "What is still missing" below.

Every endpoint this needed already existed. The gap was entirely the absence of a client.

| Item | What shipped |
|---|---|
| **Staff shell** | `/staff` route group with its own skip link, banner, single `<main>`, labelled navs and a role guard. Deliberately separate from the student `AppShell` — they share no navigation |
| **D3 · Review queue** | `/staff/review` — the document rendered beside the requirement it must satisfy, inline for images and PDFs; verify / reject / waive; **7 canned rejection reasons**, editable before sending; `J`/`K` to move, `V` to verify, `R` to reject; the decided item drops out and the next slides under the cursor, so the reviewer never loses their place |
| **D4 · Command palette** | `Ctrl`/`Cmd`+`K` across students and the queue, debounced and server-side. A real `combobox` + `aria-activedescendant`: arrows move the highlight while DOM focus stays in the input |
| **Student directory** | `/staff/students` — server-side search over name, email and phone, as a real `<table>` with scoped headers |
| **Student record** | `/staff/students/[id]` — contact, profile, access and email-verification state on one page instead of six changelists |

**Rejection reasons are the quiet win here.** A student told *"the photo is blurred, we cannot
read the expiry date"* can act on it; one told *"rejected"* opens a support ticket. Canned
reasons make that the default rather than something a reviewer has to type forty times a day.

**Three React and accessibility defects the linters caught during this work**, all of them mine:
a `setState` nested inside another state updater in the queue's `move()`; a variable reassigned
during render in the palette's group headers; and stale results rendering for a search term too
short to have run. The last was a real bug, not a lint nit.

**What is still missing — the gate is not met until these land:**

- **Payments and reconciliation.** `/api/admin/payments/`, `webhook-events/` and
  `reconciliation/` have no client, so finance still works in Django admin.
- **Messaging UI.** `MessageThread` and `Message` are built and the landing page promises "a
  counsellor you can message inside the platform". Still no surface. This is a promised feature
  with no implementation, and should outrank the two above.
- **Bulk actions, saved views, CSV export, and a staff-facing audit-log viewer** over the
  existing `record()` trail.
- **Per-student applications and payment timeline.** The student record says so on the page
  rather than faking a panel: the admin API does not expose those scoped to a single student, so
  it needs an endpoint before it needs a UI.
### Phase 3b — The seeded fixture API ✅ shipped

> **Gate:** every authenticated route scanned by axe in both themes and both viewports.
> **Met** — the suite is now **152 tests**, up from 78. Coverage went from public routes only
> to the whole product.

Roughly half the product had never been scanned: the dashboard, checklist, document vault,
checkout, referrals, intake form and the entire staff console. The public suite was green while
the pages staff use every day were untested.

**How it works.** `e2e/fixtures/` serves a seeded API through Playwright's `page.route()`, and
seeds a session into `localStorage` before any script runs. Three personas — `studentPage`,
`unpaidPage`, `staffPage` — cover the paid, unpaid and staff states.

**Why not run the real backend?** What these tests assert is how the *rendered UI* behaves —
axe violations, landmark structure, keyboard flow. For that, a real Postgres, Redis and
migration step buy nothing but a slower, flakier CI. The API contract already has the backend's
own 87 tests.

**The one risk that trade carries is drift**, and it is guarded rather than hoped away:

- `FIELD_CONTRACT` in `e2e/fixtures/data.ts` lists every field the fixtures mock, per
  serializer. `backend/tests/test_frontend_contract.py` evaluates it and asserts each field
  exists on the real serializer. Rename a serializer field and the backend suite fails.
- An unmapped route returns **404 with a message naming the missing handler**, never a silent
  200 — and a test asserts that, so the fixture cannot start lying about what the product does.
- Fixtures are deliberately mid-flow: a rejected document, an expired one, an unverified email,
  a part-complete checklist, an application with no checklist yet. A pristine happy path
  exercises none of the states that actually break.

**Four real defects it found on its first run**, none of which any existing test could have
caught:

| Defect | Severity |
|---|---|
| **Every form input was unreadable in dark mode.** `FormRenderer` had a hardcoded `bg-white` in its local `inputClass`; against near-white `text-ink` that is **1.09:1**. The token migration missed it because `bg-white` is not one of the slate classes it rewrote | Serious — the intake form was unusable |
| **The command palette's listbox was structurally invalid.** I had wrapped each `role="option"` in an `<li>`, breaking the required listbox→option relationship. axe reported `aria-required-children` and `aria-required-parent` as **critical**; a screen reader would announce results as list items, not selectable options. Fixed to `listbox` → `group` → `option` | Critical |
| **Wide tables were keyboard-inaccessible on mobile.** `overflow-x-auto` with no `tabIndex` — `scrollable-region-focusable`. A phone user navigating by keyboard could not reach the off-screen columns at all. Fixed with a `ScrollableX` primitive | Serious |
| **`ChecklistItem.document_id` did not exist.** The frontend type declared a field the API has never sent — `ChecklistItemSerializer` returns a nested `document`. Nothing read it, so it was harmless, but it was a false statement about the contract. Caught by the drift guard on its first run | Contract lie |

The dark-mode input bug is the one worth dwelling on: it shipped through Phase 2's contrast
checker, because that verifies *tokens*, not whether a component uses them. Only rendering the
page and measuring it caught it.

### Phase 4 — Pass the questionnaire 🟡 MFA and throttling shipped

> **Gate:** a partner institution's security and data-protection review clears without
> exceptions. **Not yet met** — four of six items outstanding.

| Item | State |
|---|---|
| **MFA** | ✅ TOTP + 10 recovery codes, mandatory for staff. 23 tests |
| **Throttling** | ✅ `UserRateThrottle` + `AnonRateThrottle` now floor the ~79 endpoints that declared no scope; MFA verification capped at 10/hour |
| **Session management** | ❌ No device list, no remote revoke, no "sign out everywhere" |
| **Notification preferences** | ✅ Email + WhatsApp + Telegram, per category, with quiet hours. **SMS removed entirely.** 22 tests |
| **NDPR data rights** | ❌ `erase_student` exists server-side but there is no self-service export or deletion request flow. The privacy policy's 30-day commitment still rests on a person reading an inbox |
| **SSO / SCIM** | ❌ Deliberately deferred — see below |
| **Accessibility statement** | ❌ Not written, though the evidence for it now exists |

**On MFA.** `django-otp` was already installed and already gating the Django admin; nothing
protected the API. Both device types come from django-otp, so there are **no new tables and no
migration**. Four decisions worth recording:

- **Enrolment does not switch MFA on.** The device stays unconfirmed until the user proves they
  can generate a code from it, so a mistyped secret is caught at setup rather than at the next
  sign-in.
- **The second factor is checked only after the password is already correct**, so the response
  never reveals whether an account exists or has MFA enabled.
- **Staff cannot switch it off.** Otherwise the requirement is advisory, and advisory controls
  get turned off the moment they are inconvenient.
- **Recovery codes are stored unformatted, displayed as `XXXX-XXXX`.** The hyphen is a reading
  aid, not part of the secret, and the alphabet excludes `O`/`0` and `I`/`1` because these get
  written down and read back under stress.

Three tests initially failed against *correct* behaviour: django-otp refuses a replayed TOTP
token, and throttles a device after a failed attempt so the next verification is refused even
when the code is right. Both are documented in `apps/accounts/mfa.py` — the second is worth
knowing, because it means a mistyped code costs the user a moment rather than an instant retry.

**Why SSO is deferred rather than half-built.** OIDC needs a real identity provider to test
against, and nothing can be verified without one. It is also demand-driven: it matters when a
partner institution requires directory-managed accounts, and not before. Building it untested,
ahead of that, would be the worst of both.

**On notification channels.** SMS is gone. It is the most expensive per message, the least
rich, the easiest to spoof, and locally the one most associated with scams — the opposite of
what a product for wary students should signal. WhatsApp and Telegram reach the same people,
carry formatting and links, and confirm delivery.

Routing is the intersection of four conditions, and all four must agree:

1. **The agency has the channel enabled *and* configured.** A toggle that silently does nothing
   is worse than no toggle: the student opts in, stops watching email, and misses a rejection.
   `ChannelConfig.is_live` is enabled-and-configured, and the admin shows both separately
   because they come apart constantly.
2. **The user opted in** for that category on that channel.
3. **The user is reachable there** — a linked Telegram chat, a WhatsApp number with a *recorded*
   opt-in. Holding somebody's number is not permission; WhatsApp's own policy requires evidenced
   consent before the first message.
4. **It is not quiet hours.**

One override beats all four: security and payment mail always sends. A password reset a
preference swallowed is a lockout, not a preference honoured — the API refuses to record that
choice at all. And every notification writes an `in_app` row regardless, which is the inbox and
the answer when somebody says they were never told.

**Telegram linking** works the only way it can: a bot cannot open a conversation, so the app
mints a short-lived token, deep-links to `t.me`, and the webhook matches the returning chat to
the account. That webhook is unauthenticated by necessity, so it carries a secret path segment
checked against the configured verify token.

**A serious flaw in the e2e setup surfaced during this work.** Playwright's
`reuseExistingServer` adopts whatever is already listening on the port — and on this machine
3000 and 3100 were both taken by unrelated services. The suite ran **32 "passing" accessibility
scans against a Grafana login page** before the skip-link test happened to notice. It now always
starts its own server on a port of its own and fails loudly if that port is busy. Scans also run
with reduced motion, so a contrast check cannot land mid-transition — that was an intermittent
failure on the checklist progress bar.

**Remaining order of value.** NDPR self-service next, which would let the privacy policy's
30-day commitment rest on code instead of a person reading an inbox. Then session management.
The accessibility statement is an afternoon and can go whenever.

---

## Phase 5 — The blog, and making the site findable

Two requests, and they are really one: an agency whose whole argument is "we tell you what other
agents won't" has no reason to appear in a search result unless it has actually written some of it
down. So the blog is the acquisition channel and the SEO work is what makes the channel function.
Neither is worth much alone.

### What shipped

**Backend — `apps/blog/`**

| File | What it holds |
| --- | --- |
| `models.py` | `Category`, `Tag`, `Post`, `PostRevision` |
| `rendering.py` | Markdown → sanitised HTML, once, server-side |
| `ai.py` | Claude-backed outline / draft / metadata / rewrite, plus the house-style scan |
| `services.py` | The publish gate, revisions, restore |
| `serializers.py` | Public shape and staff shape, kept separate |
| `api.py` | Public read, staff write, AI assist |
| `feeds.py` | RSS and Atom |
| `admin.py` | Django admin, for the quarterly jobs and for recovery |
| `management/commands/seed_blog.py` | Four categories, seven tags, three real articles |

**Frontend** — `/blog`, `/blog/[slug]`, `/blog/category/[slug]`, `/blog/tag/[slug]`, a staff
composer at `/staff/blog`, and the SEO infrastructure: `sitemap.ts`, `robots.ts`,
`opengraph-image.tsx`, `blog/rss.xml/route.ts`, and `lib/seo.ts` for metadata and JSON-LD. The
landing page's header and footer moved into `components/marketing/SiteChrome.tsx` — a blog that
does not carry the same header is a different website as far as a reader is concerned, and two
copies would have drifted inside a week.

**New permissions.** `AdminProfile.can_write_content` and `can_publish_content`, split
deliberately: a writer drafts and uses the assist, an editor decides what the public sees.

**New settings.** `ANTHROPIC_API_KEY`, `BLOG_AI_MODEL`, `SITE_BASE_URL`, `SITE_NAME`, and a
`blog_ai` throttle scope at 40/hour — each assist is a billed model call, and 40 is well past
what a writer working normally reaches while still stopping a stuck retry loop in the composer.

### The decisions worth arguing about

**A slug is a promise, so it is frozen at publish.** Once a post is live its URL is in search
results, in WhatsApp messages, and on other people's sites. `Post.save()` refuses to change the
slug of a published or archived post. Retitling stays allowed — the title is editorial, the URL is
a commitment. Deleting a live post is refused too: it leaves every inbound link broken with no
explanation.

**Scheduling reads the clock, not a flag.** `PostQuerySet.live()` filters on
`published_at <= now()`, so a scheduled post cannot go public early because a worker was down, and
cannot fail to appear because one never ran. There is no publishing cron job, and that is the
point.

**Markdown is rendered on the server, exactly once.** The frontend ships no Markdown parser, the
HTML a crawler gets is the HTML a reader gets, and sanitisation happens in one place. Post bodies
are written by staff, so this is not the usual hostile-input problem — but a body can also come out
of `ai.py`, an editor can paste from anywhere, and a compromised staff account should not be able
to put a script tag on a public page. `nh3` strips everything outside a fixed tag list on the way
into `body_html`, and `body` itself is never sent to the browser.

**Nothing publishes without a person.** `published_by` is required, enforced in `Post.clean()`, and
AI involvement is recorded on the post and disclosed to readers on the article. For a brand whose
argument is "we do not make claims you cannot check", passing generated prose off as first-hand
experience would be the same failure in a different costume.

**The house-style scan is the interesting part.** `ai.review_flags()` scans every body — human or
generated — for three things: guarantees, named places, and figures the business has not published.
It runs on every AI suggestion in the composer and again at publish, where its output becomes
blockers. The rules encode business constraints, not taste: naming a country gives away what the
₦5,000 buys, an invented figure is the thing this agency exists not to do, and getting the
admission/visa order wrong in public costs a reader real money.

**Then the scan blocked an article it should have allowed.** The third seeded post teaches readers
to recognise scam language — and so it necessarily contains the words "guaranteed visa". The guard
refused to publish the one article most worth publishing. That is a genuine false-positive class,
not a bug in the prose, and weakening the scan to accommodate it would have cost far more than it
saved.

The resolution is `Post.style_override_reason`: a written justification that turns the flags from
blockers into warnings the editor still has to acknowledge, and which is copied into the audit
record on publish. An editor who cannot write down why the phrase belongs there has just
discovered that it does not. It is the same shape as the `force` flag on warnings — an override
with a name attached — and it is the honest answer to a blunt rule meeting a legitimate exception.

**Warnings versus blockers.** Blockers are facts: no body, no excerpt, a hero image with no alt
text, AI involvement with no notes. Warnings are judgement: a 72-character title, a focus keyword
absent from the article, no category. Publishing past warnings needs `force`, and what was
overridden is recorded. Conflating the two would give either an editor who cannot publish a good
post or a gate that stops nothing.

**Tag pages are `noindex, follow`.** They are navigation, and almost always a subset of a category
page. Indexing both asks a search engine to choose between two pages saying the same thing, and it
usually chooses neither. `follow` keeps the internal links working. Category pages with no live
posts 404 rather than shipping a thin indexable page.

**`robots.ts` disallows everything on preview deployments.** A staging copy that gets indexed
competes with production for the same queries, and the usual way that happens is this file being
written for production only.

**The share card avoids the naira sign.** The OG image renderer has no font of its own outside
basic Latin and silently drops what it cannot fetch — `₦` came out as a blank box, which the build
warned about and would otherwise have shipped. The card says `NGN 5,000` and draws its tick as an
SVG path. Everywhere a browser does the rendering, the symbol stays.

**The AI assist never writes into the draft.** Every suggestion lands in a review area behind an
explicit "Use this" button, because the moment generated text can appear in a body without a person
pressing something, the provenance field becomes a guess. Provenance also only escalates: a later
metadata suggestion cannot downgrade a machine-written draft to "AI-assisted edit".

The most useful thing the assist returns is not the prose. `ArticleOutline.what_we_cannot_claim` is
the model listing where it was tempted to invent a figure or name a country, for the editor to
verify or cut.

**Streaming for the draft, structured output for everything else.** A full article risks a gateway
timeout before the first byte, so `write_draft` and `rewrite` stream and use
`.get_final_message()`. Outlines, metadata and title options come back through `messages.parse()`
with Pydantic models, so a malformed suggestion is a validation error rather than a half-parsed
dictionary.

**Search is `icontains`, not Postgres full-text.** At this volume it is indistinguishable to a
reader, and it keeps the suite runnable on SQLite. Worth revisiting at a few hundred posts, not
before.

### Verification

- 44 new backend tests (`tests/test_blog.py`), weighted towards the promises rather than CRUD: the
  slug freeze, the publish gate, the sanitiser, the house-style scan, the override and its audit
  trail, and that a writer cannot publish.
- 24 new Playwright tests. Axe (WCAG 2.2 A + AA) over the blog list, the composer, and the
  composer's preview — which renders the same `.post-body` markup the public article does — in both
  colour schemes and at phone width, plus the public blog index. Three behavioural tests cover the
  parts that are promises rather than pixels: that provenance is recorded, that a dirty draft cannot
  be published, and that the assist offers nothing to apply until something has been generated.
  Two real defects came out of it: a `getByLabel("Title")` that also matched "Search title", and
  confirmation that the composer's own pre-flight panel — the densest colour-on-colour surface on
  the page — passes contrast in both themes.
- The e2e fixture contract now covers all six blog serializers, so a renamed field on any of them
  fails `tests/test_frontend_contract.py` rather than silently breaking a page that still passes
  its own tests.
- `make lint-backend` clean. Fixing one ruff finding surfaced a real bug: `lstrip("NGN")` takes a
  character *set*, so it was also eating a leading `G`.
- Frontend: `tsc --noEmit` clean, `eslint` clean, `npm test` 17 passing, `npm run check:contrast`
  54 pairs across both themes, production build clean with no prerender or font warnings.
- `make blog-seed` runs, is idempotent, and asserts its own prose against the house style before it
  writes anything.
- The full backend suite is unchanged: the same 6 failures as before this phase, all of them
  Redis/Celery-broker or SQLite artefacts from Docker being down, none in `apps/blog`.

### One small side change

`frontend/.prettierrc.json` now pins `printWidth: 100`. There was no Prettier config, so
`npm run format` was silently running at the default 80 while every file in the repo had been
written at roughly 100 — meaning the project's own format script would have rewritten the entire
codebase the first time anyone ran it. Pinning 100 makes it agree with the code that exists.
Fourteen pre-existing files are still not Prettier-clean at 100; reformatting them is a separate
decision and was left alone rather than buried inside this change.

### Honestly not done

- **The public article page has never been scanned populated.** Those pages fetch from the API on
  the *server*, which Playwright's `page.route()` cannot intercept, so `/blog` is scanned in the
  state it renders when the API is unreachable — a real state, but the empty one. The article
  layout's typography is covered indirectly through the composer's preview, which renders the same
  `.post-body` markup. Scanning it properly needs the real backend running in CI.
- **No end-to-end publish → appears-on-site test**, for the same reason. The two halves are each
  covered (the backend test asserts a published post appears in the public list; the e2e test
  asserts the composer's publish button is correctly gated) but nothing exercises the seam.
- **No per-article OG image.** One well-made card for everything. A dynamic image per post means an
  edge function on every share-link crawl and a second place a title has to be escaped.
- **Hero images are uploadable but there is no picker in the composer.** The field exists on the
  model and in Django admin; the composer edits the alt text only.
- **No internal-link checker.** The assist suggests topics to link to, and nothing verifies that a
  link in a body still resolves.
- **Nothing has been published on the real site yet**, so none of the SEO work has been observed
  against a live crawler. `NEXT_PUBLIC_SITE_URL` and `SITE_BASE_URL` must be set to the real domain
  and must agree, or canonical URLs will point at localhost.

---

## Phase 6 — The blog, as something an editorial team runs

Phase 5 built posts and a composer. This is the layer that makes it a system
somebody operates: site-wide settings in one editable row, comments with
moderation and five layers of spam defence, real author identity with `Person`
markup, FAQ blocks that become rich results, and slug changes that leave a 301
behind.

**The plan, the decisions and the honest gaps are in [blog-system.md](blog-system.md).**
It is the longer document because most of this phase is decisions rather than
mechanism — what belongs in a database row versus a deploy, why every comment
default is the cautious one, and why there is no CAPTCHA.

Headline numbers: 100 backend tests (up from 44), 28 Playwright tests on the
staff side, `AdminProfile` unchanged, four new models, one new throttle scope
(`blog_comment`), and no new environment variables — every setting this phase
added is editable at `/staff/blog/settings` rather than requiring a deploy.

---

## Prices come from one place

Added after the blog work, because it turned out to matter more than either of us
thought.

### The bug class this closes

The access fee existed in four independent places: an environment variable the
payment service read, a constant in `frontend/src/lib/company.ts`, and a literal
typed into the checkout button and the signup blurb.

Nothing tied them together, so nothing could fail when they disagreed — and a
checkout button is the worst possible place for that. The number a person reads
before clicking and the number their bank actually debits have to come from the
same source, and here they demonstrably did not have to.

No test could catch it either. Every assertion about the fee hardcoded the same
literal the code did, so the suite agreed with the bug.

### The shape of the fix

One row, `apps.payments.pricing.Pricing`, and everything reads it:

| Reader | Was |
| --- | --- |
| `initiate_payment` — what the gateway charges | `settings.ACCESS_FEE_AMOUNT` |
| Landing page, hero, fee section | `ACCESS_FEE.formatted` |
| Checkout page and button | the literal `₦5,000` |
| Signup blurb | the literal `₦5,000` |
| Terms, refund policy | `ACCESS_FEE.formatted` |
| Article call-to-action | `ACCESS_FEE.formatted` |
| Share card | `ACCESS_FEE.amount` |
| `siteDescription()` for search results | `ACCESS_FEE.formatted` |
| The blog's house-style scan | the literal set `{"5,000", "5000"}` |

Served publicly at `/api/pricing/`, unauthenticated on purpose: a price behind a
token is a price that gets hardcoded in whichever surface cannot get one. Read
through `@/lib/pricing` on the server and `usePricing()` in the two client pages.

`ACCESS_FEE_AMOUNT` / `ACCESS_FEE_CURRENCY` still exist, and now seed the **first
row only**. `make pricing` says so out loud whenever they disagree with what is
actually charged, because a deployment whose env var is being silently ignored is
a deployment where somebody expects it to work.

### Cost estimates, and why they go stale by themselves

`REAL_COSTS` in `company.ts` was four rows whose amounts were all `PENDING`, with
a comment reading *"a stale number here is worse than none"*. That comment was
correct and the mechanism did not exist — a constant in a TypeScript file cannot
know how old it is, and would have sat there looking researched for two years.

`CostEstimate` rows carry `verified_on` and `verified_source`. Past
`Pricing.estimate_stale_after_days` (default 120) the row stops serving its
figure and serves "Ask us — this changes" instead. Nobody has to remember, and
the stale figure never reaches the API, so it cannot leak into a page or a cache.

`make pricing-seed` creates the four rows the landing page expects **with no
figures**, which is the honest state: nobody has checked them. The costs section
on the landing page hides itself entirely when there are no rows, because a table
with a header and nothing under it reads as a broken page.

### Three smaller decisions

**The fallback shows "—", not a price.** `PRICING_UNAVAILABLE` in
`@/lib/pricing` has every money field as a dash. A fallback that quietly
substituted ₦5,000 would look correct and be wrong, which is the bug again in a
different costume. `usePricing()` exposes `ready` so checkout renders a loading
state rather than a guessed number.

**The blog scan follows the fee.** `ai.allowed_figures()` derives from the row,
so raising the fee to ₦7,500 both permits "7,500" in new copy *and* starts
flagging every surviving "5,000" in an old article — which is now a wrong number
on a live page. The house-style prompt interpolates it too, so Claude is told the
current fee on the next request.

**The launch gate lost the cost figures and says so.**
`check-launch-ready.mjs` scans `company.ts` for `PENDING`, and the cost amounts
are no longer there. Rather than leave a silent gap, the script now prints where
that check moved to: `make pricing ARGS=--strict`, which exits non-zero on an
unverified figure.

### Verification

- **28 new backend tests** (`tests/test_pricing.py`). The one that would have
  caught the original bug asserts that `/api/pricing/` and the `Payment` row
  agree on the amount for the same request.
- A shared autouse fixture clears the cached singletons between tests, so a test
  that changes the fee cannot affect a different file.
- **Two existing tests had the fee hardcoded** and failed the moment the price
  came from a row instead of a literal — one in the blog's house-style scan, one
  in `test_the_client_cannot_choose_the_amount`, the test that guards against a
  student paying ₦1 for access. Both had passed only because the code hardcoded
  the same number they asserted. Both now read the price from the row, through a
  shared `access_fee` fixture, so neither can agree with a wrong value again. The
  security property they assert was never broken: the posted amount was still
  discarded.
- The full backend suite is back to exactly the six pre-existing failures (four
  Redis/Celery from Docker being down, one SQLite raw-SQL artefact, one journey
  test that needs the broker), none of them in pricing.
- Both singletons' caches fail open: `Pricing.load()` is on the read path of
  every public page and of checkout, so a Redis outage costs one query.
- `make lint-backend` clean, `tsc` clean, `eslint` clean, production build clean.

### Still not done

- **No price history.** A change is audited, so the trail exists in `AuditLog`,
  but there is no "what did we charge in March" screen.
- **No per-currency pricing.** One fee, one currency. A second currency would
  need a table rather than a row, and nothing asks for one yet.
- **Cost estimates are not versioned.** Editing a figure overwrites the old one;
  the audit row keeps the previous value.
