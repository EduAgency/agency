# Nasuru Agency Platform

Lead intake, student onboarding, document checklists, admin-built forms,
school/requirement management, payments and referrals for an international
student recruitment agency.

---

## What this is, structurally

Four engines wearing one UI. Everything else is a view on top of them.

| Engine | Lives in | The rule that makes it work |
|---|---|---|
| **Forms** | `backend/apps/forms_engine/` | Forms are versioned JSON schemas, not Django models. A published form is immutable; editing creates version N+1 and old submissions stay bound to the version they answered. |
| **Checklists** | `backend/apps/applications/` | A checklist is a **snapshot** taken at generation time. Changing a school's requirements never rewrites a student's live checklist — staff run an explicit re-sync that reports what it changed. |
| **Payments** | `backend/apps/payments/` | A payment is successful when a **signature-verified webhook** says so, re-verified against the gateway API. Never because the browser hit a success page. |
| **Referrals** | `backend/apps/referrals/` | A reward is earned on a **confirmed payment**, never a signup. The rule is snapshotted onto the reward, so changing the programme never rewrites history. |

## Stack

- **Backend** — Django 5.2 LTS + DRF, PostgreSQL 17, Celery + Redis, S3-compatible storage
- **Frontend** — Next.js 16 (App Router) + TypeScript + Tailwind
- **Python 3.13** (pinned in `pyproject.toml`; matches the Docker image)

### Why the backend is not on Vercel

Vercel runs backend code as short-lived serverless functions. Three things here
need a persistent process:

1. **Webhooks** must return in milliseconds and finish the work in a Celery
   worker — workers cannot live on Vercel.
2. **Document uploads** (passports, transcripts) fight function payload and
   duration limits.
3. **Reconciliation and bulk operations** are background jobs by nature.

Frontend on Vercel, backend on Render / Railway / Fly.io. Changing this after
launch is expensive; before launch it is a deploy target.

---

## Local setup

Every routine command is a Make target. `make` on its own lists them all.

```bash
make env        # create backend/.env from the template
make keys       # print a DJANGO_SECRET_KEY and FIELD_ENCRYPTION_KEY to paste in
make setup      # docker infra + both dependency stacks + migrations
make seed       # demo data, including a student you can sign in as
make superuser  # an admin account
```

Then, in separate terminals:

```bash
make dev-backend    # Django on :8010
make dev-frontend   # Next.js on :3000
```

The backend is a **uv project**: dependencies, the dev group and the ruff and
pytest configuration all live in `backend/pyproject.toml`, resolved into
`backend/uv.lock`. Every Make target runs through `uv run`, which syncs the
environment on demand — nothing needs a virtualenv activated, or even created,
first.

```bash
make add PKG=some-package          # add a dependency
make add PKG="pytest-cov --dev"    # ...to the dev group
make lock                          # re-resolve after editing pyproject.toml
```

The Docker image installs from the lock with `uv sync --locked --no-dev`, so a
deploy gets exactly the versions that were tested and none of the test tooling.

| Service | URL |
|---|---|
| Admin (the agency's daily workspace) | http://localhost:8010/admin/ |
| Staff console | http://localhost:3000/staff/review |
| API docs (OpenAPI) | http://localhost:8010/api/docs/ |
| Health check | http://localhost:8010/health/ |
| Frontend | http://localhost:3000 |

`seed_demo` loads the HWR Berlin requirement set transcribed from the agency's
own spreadsheet tracker, a published intake form with conditional fields, and
the referral reward rules — so the model can be clicked through immediately.

### Background workers

```bash
make worker     # webhook processing, notifications
make beat       # nightly reconciliation, nudges
```

Or `docker compose up` for the whole stack.

### Checks

```bash
make verify     # lint + types + unit tests, both stacks
make test       # pytest (needs `make infra`) and vitest
make e2e        # Playwright + axe across public, student and staff routes
make contrast   # every design token pair against its WCAG threshold
make launch-gate  # fails while any policy clause still awaits a decision
```

The backend suite (123 tests) covers the four engines' invariants specifically:
schema validation, form versioning, checklist snapshot isolation, progress
calculation, webhook signature/idempotency, referral fraud handling, and
two-factor enrolment, replay and recovery — plus the API permission boundaries
(a student cannot reach another student's records; a document reviewer cannot
reach gateway credentials) and the full signup → pay → apply → upload → review
journey.

The frontend suite is 17 unit tests and 152 Playwright + axe tests, scanning
every route in both colour schemes and both viewports. See
[docs/enterprise-readiness.md](docs/enterprise-readiness.md).

Before deploying, confirm the production posture is clean:

```bash
DJANGO_DEBUG=False DJANGO_ALLOWED_HOSTS=api.yourdomain.com \
  .venv/bin/python manage.py check --deploy
```

---

## Layout

```
backend/
  config/               settings, urls, celery
  apps/
    core/               base models, audit log, encrypted fields, middleware
    accounts/           User, StudentProfile, AdminProfile (granular permissions)
    schools/            School, Programme, versioned SchoolRequirementSet, RequirementItem
    forms_engine/       FormDefinition (JSONB, versioned), schema + submission validation
    applications/       Application, ChecklistInstance (snapshot), documents vault
    payments/           gateway configs, Payment, WebhookEvent, refunds, reconciliation
    referrals/          codes, events, reward rules, rewards, payouts
    notifications/      notifications, templates, in-platform messaging
  tests/
frontend/
  src/types/            TypeScript mirror of the form schema contract
  src/lib/forms/        conditions + validation — ported from the backend, must stay in step
  src/components/forms/ FormRenderer — renders any admin-built form, no per-form components
docs/                   HWR Berlin tracker (the source for the seeded requirement set)
```

---

## Operational notes

**Gateway keys.** Stored `Fernet`-encrypted via `FIELD_ENCRYPTION_KEY`. Lose that
key and every stored secret becomes unreadable — back it up separately from the
database. Access to the gateway-config screen is gated on
`AdminProfile.can_manage_payment_config`, so a document reviewer never sees it.

**Webhook URLs to register with each gateway:**
```
https://<api-domain>/api/payments/webhooks/paystack/
https://<api-domain>/api/payments/webhooks/flutterwave/
```

**Progress basis.** `ChecklistInstance.progress_basis` decides whether the
student's percentage counts *verified* or merely *uploaded* documents. It
defaults to `verified` — the honest reading, and it prevents a student believing
they are 90% done when half their uploads are the wrong document. Both numbers
are always stored so the UI can show "12 uploaded, 8 verified". This is a
business decision as much as a technical one: verified-only depends on your
review turnaround.

**Audit log.** Every sensitive action goes through `apps.core.audit.record()`.
The admin view is read-only and the model is append-only. Secrets are scrubbed
before they can reach it.

**Data protection (NDPR).** Documents are stored private with short-lived signed
URLs, consent is versioned and timestamped on the User model, student records
are archived rather than deleted, and Sentry runs with `send_default_pii=False`.
The policy documents themselves are still to be written.

---

## The API

83 endpoints, in three bands with distinct permission postures:

| Prefix | Who | Notes |
|---|---|---|
| `/api/auth/` | public / self-service | signup, login, JWT refresh, email verification, password reset. Signup and reset are rate-limited; neither confirms whether an address exists. |
| `/api/` | students | every queryset is scoped to the caller, so no object-level check can be forgotten on a new action. Most routes sit behind `HasPlatformAccess`. |
| `/api/admin/` | staff | each route names the `AdminProfile` permission it needs, e.g. `can_review_documents`, `can_manage_payment_config`. |

Browse it at `/api/docs/`, or generate a typed client from `/api/schema/`.

Two rules the API enforces that are easy to lose later:

* **Prices come from the server.** `POST /api/payments/initiate/` takes no
  amount. Posting one is ignored.
* **Secrets are write-only.** Gateway configs accept `secret_key` and
  `webhook_secret` but never return them — only a fingerprint, so staff can
  confirm which key is live.

## Not yet built

Phase 1–2 engines, data model and API are in place. Still outstanding:

- The admin form-builder UI (the engine, validation and its API are done; the visual editor is not)
- Student and admin dashboard pages beyond the landing page
- SMS/WhatsApp delivery (notification records and the queue exist; no provider is wired)
- Flutterwave refunds are implemented but untested against a live account
- Two-factor enrolment flow for staff (django-otp is installed and gating the Django admin; there is no enrolment UI yet)
- Terms, privacy and refund policy copy
