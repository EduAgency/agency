/**
 * Seed data for the end-to-end suite.
 *
 * Every shape here mirrors a DRF serializer in `backend/apps/`. That mirroring
 * is the whole risk of a fixture API — a mock that drifts from the real
 * response is worse than no mock, because it makes a broken page look tested.
 *
 * So it is checked rather than trusted: `FIELD_CONTRACT` at the bottom is read
 * by `backend/tests/test_frontend_contract.py`, which asserts that every field
 * named here actually exists on the serializer it claims to come from. Add a
 * field to a fixture without adding it to the serializer and the backend suite
 * fails.
 *
 * The data is deliberately mid-flow rather than pristine: a rejected document,
 * an unverified email, a part-complete checklist. An empty happy path exercises
 * none of the states that actually break.
 */

export const STUDENT_TOKEN = "e2e-student-access-token";
export const STAFF_TOKEN = "e2e-staff-access-token";

export const studentSession = {
  user: {
    id: "u-student-1",
    email: "amara.okafor@example.com",
    first_name: "Amara",
    last_name: "Okafor",
    full_name: "Amara Okafor",
    role: "student",
    // Unverified on purpose: the dashboard renders its confirmation notice,
    // which is a live region plus an action, and needs scanning.
    email_verified_at: null,
  },
  student: {
    id: "sp-1",
    email: "amara.okafor@example.com",
    full_name: "Amara Okafor",
    stage: "documents",
    has_platform_access: true,
    access_granted_at: "2026-08-02T09:15:00Z",
  },
};

export const unpaidStudentSession = {
  ...studentSession,
  student: { ...studentSession.student, has_platform_access: false, access_granted_at: null },
};

export const staffSession = {
  user: {
    id: "u-staff-1",
    email: "reviewer@nasuru.com",
    first_name: "Chidi",
    last_name: "Nwosu",
    full_name: "Chidi Nwosu",
    role: "reviewer",
    email_verified_at: "2026-06-01T08:00:00Z",
  },
  admin: { id: "ap-1", job_title: "Document reviewer", can_review_documents: true },
};

const passportUpload = {
  id: "up-1",
  version: 2,
  original_filename: "passport-data-page.jpg",
  content_type: "image/jpeg",
  size_bytes: 1_842_000,
  status: "pending_review",
  rejection_reason: "",
  reviewed_at: null,
  created_at: "2026-09-01T11:20:00Z",
  // A 1×1 transparent PNG. Inline so the suite never reaches the network for
  // an image, which would make the run non-deterministic.
  download_url:
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
};

const transcriptUpload = {
  id: "up-2",
  version: 1,
  original_filename: "waec-result.pdf",
  content_type: "application/pdf",
  size_bytes: 640_000,
  status: "rejected",
  rejection_reason: "The image is too blurred to read. Please re-scan it in better light.",
  reviewed_at: "2026-09-03T14:02:00Z",
  created_at: "2026-09-02T16:45:00Z",
  download_url: "data:application/pdf;base64,JVBERi0xLjQK",
};

export const documents = [
  {
    id: "doc-1",
    title: "International passport",
    shareable_key: "passport",
    category: "Identity",
    issued_on: "2022-04-11",
    expires_on: "2032-04-10",
    review_status: "pending_review",
    is_expired: false,
    current: passportUpload,
    uploads: [passportUpload, { ...passportUpload, id: "up-0", version: 1, status: "rejected" }],
    created_at: "2026-08-20T10:00:00Z",
    updated_at: "2026-09-01T11:20:00Z",
  },
  {
    id: "doc-2",
    title: "WAEC result",
    shareable_key: "waec",
    category: "Academic",
    issued_on: "2021-08-30",
    // Expired on purpose: the vault renders an expiry warning for this row.
    expires_on: "2025-08-30",
    review_status: "rejected",
    is_expired: true,
    current: transcriptUpload,
    uploads: [transcriptUpload],
    created_at: "2026-08-21T09:00:00Z",
    updated_at: "2026-09-03T14:02:00Z",
  },
];

function item(overrides: Record<string, unknown>) {
  return {
    id: "ci-1",
    label: "International passport",
    description: "The photo page, showing your name, photograph and expiry date.",
    help_text: "All four corners must be visible.",
    category_name: "Identity",
    category_slug: "identity",
    category_order: 1,
    is_required: true,
    priority: "high",
    evidence_type: "document",
    accepted_file_types: [".jpg", ".png", ".pdf"],
    max_file_size_mb: 20,
    allow_multiple_files: false,
    shareable_key: "passport",
    due_date: "2026-10-01",
    status: "pending_review",
    status_display: "In review",
    rejection_reason: "",
    document: documents[0],
    updated_at: "2026-09-01T11:20:00Z",
    ...overrides,
  };
}

export const checklistItems = [
  item({}),
  item({
    id: "ci-2",
    label: "WAEC result",
    description: "Your statement of result or certificate.",
    category_name: "Academic",
    category_slug: "academic",
    priority: "medium",
    status: "rejected",
    status_display: "Needs attention",
    rejection_reason: transcriptUpload.rejection_reason,
    document: documents[1],
  }),
  item({
    id: "ci-3",
    label: "Passport photograph",
    description: "A recent photo against a plain background.",
    category_name: "Identity",
    category_slug: "identity",
    priority: "low",
    status: "verified",
    status_display: "Verified",
    document: null,
  }),
  item({
    id: "ci-4",
    label: "Proof of funds",
    description: "A bank statement covering the last six months.",
    category_name: "Financial",
    category_slug: "financial",
    is_required: true,
    priority: "high",
    status: "not_started",
    status_display: "Not started",
    document: null,
  }),
];

export const checklist = {
  id: "cl-1",
  progress_basis: "verified",
  percent_complete: 25,
  percent_uploaded: 75,
  required_count: 4,
  verified_count: 1,
  uploaded_count: 3,
  source_version: 3,
  items: checklistItems,
  categories: [
    { category: "Identity", slug: "identity", total: 2, verified: 1, uploaded: 2, percent: 50 },
    { category: "Academic", slug: "academic", total: 1, verified: 0, uploaded: 1, percent: 0 },
    { category: "Financial", slug: "financial", total: 1, verified: 0, uploaded: 0, percent: 0 },
  ],
};

export const applications = [
  {
    id: "app-1",
    school: { id: "sch-1", name: "HWR Berlin", country: "Germany", logo: null },
    programme: { id: "pr-1", name: "MSc International Business" },
    intake: "Winter 2026",
    status: "documents",
    status_display: "Collecting documents",
    target_submission_date: "2026-11-15",
    checklist: {
      percent_complete: 25,
      percent_uploaded: 75,
      required_count: 4,
      verified_count: 1,
    },
  },
  {
    id: "app-2",
    school: { id: "sch-2", name: "University of Lagos", country: "Nigeria", logo: null },
    programme: { id: "pr-2", name: "MSc Economics" },
    intake: "2027",
    status: "draft",
    status_display: "Draft",
    target_submission_date: null,
    // No checklist yet: the dashboard renders its "being prepared" branch.
    checklist: null,
  },
];

export const schools = [
  {
    id: "sch-1",
    name: "HWR Berlin",
    country_name: "Germany",
    programmes: [{ id: "pr-1", name: "MSc International Business", intakes: ["Winter 2026"] }],
  },
  {
    id: "sch-2",
    name: "University of Lagos",
    country_name: "Nigeria",
    programmes: [{ id: "pr-2", name: "MSc Economics", intakes: ["2027"] }],
  },
];

export const gateways = [
  { gateway: "paystack", label: "Card or bank transfer", currency: "NGN", is_test_mode: true },
  { gateway: "flutterwave", label: "Flutterwave", currency: "NGN", is_test_mode: true },
];

export const payments = [
  {
    id: "pay-1",
    reference: "NSR-8F2K-2026",
    gateway: "paystack",
    amount: "5000.00",
    currency: "NGN",
    purpose: "platform_access",
    status: "successful",
    paid_at: "2026-08-02T09:14:40Z",
    created_at: "2026-08-02T09:12:00Z",
  },
];

export const referrals = {
  code: "AMARA24",
  share_url: "https://nasuru.com/signup?ref=AMARA24",
  signups: 5,
  conversions: 2,
  total_earned: "2000.00",
  available_balance: "1000.00",
  currency: "NGN",
};

/** Mirrors `FormDefinition` — note the top-level title, which the page renders as its h1. */
export const intakeForm = {
  id: "form-1",
  slug: "student-intake",
  version: 3,
  title: "Tell us about your plans",
  description: "It takes about three minutes, and you can save and come back.",
  status: "published",
  audience: "student",
  purpose: "intake",
  allow_drafts: true,
  submit_button_label: "Save and continue",
  success_message: "Thanks — we have what we need to build your checklist.",
  schema: {
    key: "student-intake",
    title: "Tell us about your plans",
    sections: [
      {
        key: "study",
        title: "What you want to study",
        description: "This decides which schools we put in front of you.",
        fields: [
          {
            key: "level",
            type: "select",
            label: "What level are you applying for?",
            required: true,
            options: [
              { value: "undergraduate", label: "Undergraduate" },
              { value: "masters", label: "Master's" },
            ],
          },
          {
            key: "funding",
            type: "radio",
            label: "How will you fund your studies?",
            required: true,
            help_text: "This does not affect whether we take you on.",
            options: [
              { value: "self", label: "Self-funded" },
              { value: "sponsor", label: "A sponsor" },
              { value: "scholarship", label: "Seeking a scholarship" },
            ],
          },
          {
            key: "notes",
            type: "textarea",
            label: "Anything else we should know?",
            required: false,
          },
        ],
      },
    ],
  },
};

export const reviewQueue = [
  {
    ...checklistItems[0],
    student_name: "Amara Okafor",
    student_email: "amara.okafor@example.com",
    school_name: "HWR Berlin",
  },
  {
    ...checklistItems[1],
    id: "ci-2",
    student_name: "Tunde Bello",
    student_email: "tunde.bello@example.com",
    school_name: "University of Lagos",
  },
];

export const staffStudents = [
  {
    id: "sp-1",
    user: {
      id: "u-student-1",
      email: "amara.okafor@example.com",
      first_name: "Amara",
      last_name: "Okafor",
      full_name: "Amara Okafor",
      phone: "+2348030000001",
      email_verified_at: null,
    },
    date_of_birth: "2001-03-14",
    nationality: "Nigerian",
    country_of_residence: "Nigeria",
    state_of_residence: "Lagos",
    whatsapp: "+2348030000001",
    stage: "documents",
    stage_display: "Collecting documents",
    has_platform_access: true,
    access_granted_at: "2026-08-02T09:15:00Z",
    source: "referral",
    referral_code: "AMARA24",
  },
  {
    id: "sp-2",
    user: {
      id: "u-student-2",
      email: "tunde.bello@example.com",
      first_name: "Tunde",
      last_name: "Bello",
      full_name: "Tunde Bello",
      phone: "+2348030000002",
      email_verified_at: "2026-07-20T10:00:00Z",
    },
    date_of_birth: "1999-11-02",
    nationality: "Nigerian",
    country_of_residence: "Nigeria",
    state_of_residence: "Oyo",
    whatsapp: "",
    stage: "registered",
    stage_display: "Registered",
    has_platform_access: false,
    access_granted_at: null,
    source: "organic",
    referral_code: "TUNDE99",
  },
];

/**
 * Read by `backend/tests/test_frontend_contract.py`.
 *
 * Maps each fixture to the serializer it imitates, so drift between the two is
 * a failing backend test rather than a page that silently renders wrong.
 * Fields the frontend does not consume are simply absent — this asserts "every
 * field we mock exists", not "we mock every field".
 */
export const FIELD_CONTRACT = {
  "apps.applications.serializers.ChecklistItemSerializer": Object.keys(checklistItems[0]).filter(
    (key) => !["student_name", "student_email", "school_name"].includes(key),
  ),
  "apps.applications.serializers.StudentDocumentSerializer": Object.keys(documents[0]),
  "apps.applications.serializers.DocumentUploadSerializer": Object.keys(passportUpload),
  "apps.accounts.serializers.StudentProfileSerializer": Object.keys(staffStudents[0]),
} as const;
