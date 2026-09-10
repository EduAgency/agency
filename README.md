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
- **Python 3.13** (pinned; matches the Docker image)

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

```bash
# 1. Infrastructure (host ports are offset to avoid clashing with other stacks)
docker compose up -d db redis

# 2. Backend
cd backend
uv venv --python 3.13 .venv
VIRTUAL_ENV=.venv uv pip install -r requirements.txt
cp .env.example .env          # then fill in the two generated values below
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # FIELD_ENCRYPTION_KEY
python -c "import secrets; print(secrets.token_urlsafe(50))"                                # DJANGO_SECRET_KEY

.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo --with-student
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver 8010

# 3. Frontend
cd ../frontend
npm install
cp .env.local.example .env.local
npm run dev                   # http://localhost:3000
```

| Service | URL |
|---|---|
| Admin (the agency's daily workspace) | http://localhost:8010/admin/ |
| API docs (OpenAPI) | http://localhost:8010/api/docs/ |
| Health check | http://localhost:8010/health/ |
| Frontend | http://localhost:3000 |

`seed_demo` loads the HWR Berlin requirement set transcribed from the agency's
own spreadsheet tracker, a published intake form with conditional fields, and
the referral reward rules — so the model can be clicked through immediately.

### Background workers

```bash
celery -A config worker --loglevel=info      # webhook processing, notifications
celery -A config beat   --loglevel=info      # nightly reconciliation, nudges
```

Or `docker compose up` for the whole stack.

### Tests

```bash
cd backend && .venv/bin/python -m pytest        # 59 tests
cd frontend && npx tsc --noEmit && npm run build
```

The backend suite covers the four engines' invariants specifically: schema
validation, form versioning, checklist snapshot isolation, progress
calculation, webhook signature/idempotency, and referral fraud handling.

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

## Not yet built

Phase 1–2 data model and engines are in place. Still outstanding:

- DRF serializers/viewsets and the auth endpoints (only the webhook endpoints are wired)
- The admin form-builder UI (the engine and its validation are done; the visual editor is not)
- Student and admin dashboard pages beyond the landing page
- SMS/WhatsApp delivery (the notification records and queue exist; no provider is wired)
- Flutterwave refunds are implemented but untested against a live account
- Terms, privacy and refund policy copy
