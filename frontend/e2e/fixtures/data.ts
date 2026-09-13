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
  student: {
    ...studentSession.student,
    has_platform_access: false,
    access_granted_at: null,
  },
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
  admin: {
    id: "ap-1",
    job_title: "Document reviewer",
    can_review_documents: true,
  },
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
    {
      category: "Identity",
      slug: "identity",
      total: 2,
      verified: 1,
      uploaded: 2,
      percent: 50,
    },
    {
      category: "Academic",
      slug: "academic",
      total: 1,
      verified: 0,
      uploaded: 1,
      percent: 0,
    },
    {
      category: "Financial",
      slug: "financial",
      total: 1,
      verified: 0,
      uploaded: 0,
      percent: 0,
    },
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
    school: {
      id: "sch-2",
      name: "University of Lagos",
      country: "Nigeria",
      logo: null,
    },
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
    programmes: [
      {
        id: "pr-1",
        name: "MSc International Business",
        intakes: ["Winter 2026"],
      },
    ],
  },
  {
    id: "sch-2",
    name: "University of Lagos",
    country_name: "Nigeria",
    programmes: [{ id: "pr-2", name: "MSc Economics", intakes: ["2027"] }],
  },
];

export const gateways = [
  {
    gateway: "paystack",
    label: "Card or bank transfer",
    currency: "NGN",
    is_test_mode: true,
  },
  {
    gateway: "flutterwave",
    label: "Flutterwave",
    currency: "NGN",
    is_test_mode: true,
  },
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
 * Notification preference centre.
 *
 * Deliberately mixed: WhatsApp is available but NOT opted in, Telegram is
 * available and connected, and email is locked on the two transactional
 * categories. That combination renders every state the screen has — a live
 * toggle, a disabled one, and a locked one — in a single scan.
 */
export const preferenceCentre = {
  channels: [
    {
      channel: "email",
      label: "Email",
      available: true,
      connected: true,
      locked: true,
    },
    {
      channel: "whatsapp",
      label: "WhatsApp",
      available: true,
      connected: false,
      locked: false,
    },
    {
      channel: "telegram",
      label: "Telegram",
      available: true,
      connected: true,
      locked: false,
    },
  ],
  categories: [
    {
      category: "account",
      label: "Account",
      description: "Sign-in, password and security. Always sent by email.",
      always_email: true,
      channels: { email: true, whatsapp: false, telegram: false },
    },
    {
      category: "payment",
      label: "Payment",
      description: "Receipts and refunds. Always sent by email.",
      always_email: true,
      channels: { email: true, whatsapp: false, telegram: false },
    },
    {
      category: "document",
      label: "Document",
      description: "When a document is verified, or needs redoing.",
      always_email: false,
      channels: { email: true, whatsapp: false, telegram: true },
    },
    {
      category: "application",
      label: "Application",
      description: "When an application moves forward, or a deadline is close.",
      always_email: false,
      channels: { email: true, whatsapp: false, telegram: false },
    },
    {
      category: "message",
      label: "Message",
      description: "When your counsellor replies to you.",
      always_email: false,
      channels: { email: true, whatsapp: false, telegram: true },
    },
    {
      category: "referral",
      label: "Referral",
      description: "When someone you referred signs up, and when a reward is earned.",
      always_email: false,
      channels: { email: true, whatsapp: false, telegram: false },
    },
    {
      category: "system",
      label: "System",
      description: "Occasional tips and reminders. Off unless you ask for them.",
      always_email: false,
      channels: { email: false, whatsapp: false, telegram: false },
    },
  ],
  quiet_hours: { start: "22:00:00", end: "07:00:00" },
  telegram: {
    available: true,
    bot_username: "nasuru_bot",
    connected: true,
    username: "amara",
  },
  whatsapp: { available: true, number: "+234 803 000 0001", opted_in: false },
};

// ---------------------------------------------------------------------------
// Blog
// ---------------------------------------------------------------------------

/**
 * An editor, not a reviewer.
 *
 * The composer needs `can_write_content` and `can_publish_content`, and the
 * point of having a separate session is that the reviewer above must NOT be
 * able to reach it — which is what `staffSession` proves on the same routes.
 */
export const editorSession = {
  user: {
    id: "u-staff-2",
    email: "editor@nasuru.com",
    first_name: "Ngozi",
    last_name: "Eze",
    full_name: "Ngozi Eze",
    role: "admin",
    email_verified_at: "2026-06-01T08:00:00Z",
  },
  admin: {
    id: "ap-2",
    job_title: "Editor",
    can_write_content: true,
    can_publish_content: true,
  },
};

export const blogCategories = [
  {
    id: "cat-1",
    name: "Documents",
    slug: "documents",
    description: "Transcripts, translations, references, passports.",
    display_order: 20,
    post_count: 2,
  },
  {
    id: "cat-2",
    name: "Money",
    slug: "money",
    description: "What studying abroad costs when nobody rounds the numbers down.",
    display_order: 30,
    post_count: 1,
  },
];

export const blogTags = [
  { id: "tag-1", name: "transcripts", slug: "transcripts", post_count: 2 },
  {
    id: "tag-2",
    name: "proof of funds",
    slug: "proof-of-funds",
    post_count: 1,
  },
];

export const postFaqs = [
  {
    id: "faq-1",
    question: "How long does a transcript take?",
    answer:
      "It varies enormously by institution, and nobody can promise you a date. That is exactly why you request it first.",
    display_order: 10,
  },
  {
    id: "faq-2",
    question: "Is a statement of result the same as a transcript?",
    answer:
      "No. A statement of result says what you scored; an official transcript is the full record, issued and sealed by the institution.",
    display_order: 20,
  },
];

/** The body arrives already rendered and sanitised — see apps/blog/rendering.py. */
const renderedBody = [
  "<p>Request your transcript before you look at a single school.</p>",
  '<h2 id="what-you-are-asking-for">What you are actually asking for</h2>',
  "<p>Two different things get called a transcript.</p>",
  '<h2 id="why-it-sets-your-timeline">Why this document sets your whole timeline</h2>',
  "<p>Work backwards from an intake and the transcript is first on the calendar.</p>",
  "<ul><li>What they issue</li><li>Who they release it to</li><li>What it costs</li></ul>",
].join("\n");

export const blogPostCard = {
  id: "post-1",
  title: "Start with your transcript, not with the applications",
  slug: "start-with-your-transcript",
  excerpt:
    "Almost everyone starts by looking at schools. The people who get in on time start by requesting their transcript.",
  published_at: "2026-08-14T09:00:00Z",
  reading_minutes: 6,
  category: blogCategories[0],
  tags: [blogTags[0]],
  author: {
    name: "Ngozi Eze",
    job_title: "Admissions lead",
    slug: "ngozi-eze",
    avatar: null,
    avatar_alt: "",
    has_page: true,
  },
  hero_image: null,
  hero_alt: "",
  comment_count: 2,
};

export const blogPostCards = [
  blogPostCard,
  {
    ...blogPostCard,
    id: "post-2",
    title: "Tuition-free is not the same as free",
    slug: "tuition-free-is-not-free",
    excerpt:
      "A tuition-free place means the school does not charge you to teach you. Everything else about the year still costs money.",
    category: blogCategories[1],
    tags: [blogTags[1]],
    reading_minutes: 5,
  },
];

export const blogPostDetail = {
  ...blogPostCard,
  body_html: renderedBody,
  toc: [
    {
      level: 2,
      text: "What you are actually asking for",
      anchor: "what-you-are-asking-for",
    },
    {
      level: 2,
      text: "Why this document sets your whole timeline",
      anchor: "why-it-sets-your-timeline",
    },
  ],
  updated_at: "2026-08-20T11:00:00Z",
  seo_title: "Get your transcript first, then apply",
  seo_description:
    "The transcript is the slowest document in any international application and the one you cannot rush.",
  canonical_url: "",
  noindex: false,
  ai_involvement: "draft",
  related: [blogPostCards[1]],
  hero_caption: "",
  hero_credit: "",
  faqs: postFaqs,
  comments_open: true,
  comments: [],
  author_bio: null,
};

export const adminBlogPost = {
  id: "post-1",
  title: blogPostCard.title,
  slug: blogPostCard.slug,
  excerpt: blogPostCard.excerpt,
  body: "Request your transcript before you look at a single school.\n\n## What you are actually asking for\n\nTwo different things get called a transcript.",
  body_html: renderedBody,
  toc: blogPostDetail.toc,
  status: "draft",
  published_at: null,
  category_id: "cat-1",
  tag_ids: ["tag-1"],
  author_name: "Ngozi Eze",
  published_by_name: "",
  hero_image: null,
  hero_alt: "",
  meta_title: "Get your transcript first, then apply",
  meta_description: blogPostDetail.seo_description,
  canonical_url: "",
  noindex: false,
  focus_keyword: "how to get your transcript",
  ai_involvement: "draft" as const,
  ai_notes: "Claude drafted the first two sections; I rewrote the timeline and cut a figure.",
  hero_caption: "",
  hero_credit: "",
  comments_closed: false,
  comment_count: 4,
  pending_comment_count: 2,
  faqs: postFaqs,
  style_override_reason: "",
  reading_minutes: 6,
  view_count: 128,
  revision_count: 3,
  created_at: "2026-08-10T09:00:00Z",
  updated_at: "2026-08-20T11:00:00Z",
};

export const blogPreflight = {
  ok: false,
  blockers: ["Write an excerpt — it is what shows in listings and search results."],
  warnings: ["No focus keyword set, so there is nothing to check the article against."],
};

export const blogRevisions = [
  {
    id: "rev-1",
    title: blogPostCard.title,
    created_at: "2026-08-20T10:45:00Z",
    editor_name: "Ngozi Eze",
    note: "Before edit",
  },
  {
    id: "rev-2",
    title: "Transcripts first",
    created_at: "2026-08-10T09:05:00Z",
    editor_name: "Ngozi Eze",
    note: "Created",
  },
];

/**
 * The blog settings, as the staff endpoint returns them.
 *
 * Every default here matches the model's, so a settings screen scanned against
 * this fixture is the screen an editor actually opens on day one.
 */
export const blogSettings = {
  posts_per_page: 12,
  homepage_show_latest: true,
  homepage_article_count: 3,
  homepage_section_title: "Questions people ask us before they pay",
  listing_layout: "featured" as const,
  show_reading_time: true,
  show_author_byline: true,
  show_published_date: true,
  related_post_count: 3,

  excerpt_source: "manual_then_auto" as const,
  excerpt_length: 240,
  excerpt_required_to_publish: true,
  read_more_label: "Read the guide",

  featured_image_required: false,
  featured_image_aspect: "16:9",
  show_featured_on_listing: true,
  show_featured_on_detail: true,
  default_featured_image: null,

  comments_enabled: true,
  comments_require_approval: true,
  comments_require_email: true,
  comments_allow_replies: true,
  comments_close_after_days: 0,
  comments_notify_staff: true,
  comments_max_links: 1,
  comments_min_seconds: 4,
  comments_blocklist: "",
  comments_per_hour_per_ip: 5,

  author_pages_enabled: true,
  show_author_bio_on_article: true,

  meta_title_template: "{title} — {site}",
  default_meta_description: "",
  default_og_image: null,
  twitter_site: "",
  google_site_verification: "",
  bing_site_verification: "",
  analytics_measurement_id: "",
  feed_full_text: false,
  feed_item_count: 20,
  sitemap_include_authors: true,
  noindex_tag_pages: true,

  featured_aspect_ratio: 16 / 9,
  updated_at: "2026-09-01T09:00:00Z",
};

export const authorProfile = {
  id: "ap-author-1",
  user: "u-staff-2",
  user_email: "editor@nasuru.com",
  display_name: "Ngozi Eze",
  slug: "ngozi-eze",
  headline: "Admissions lead",
  bio: "Ngozi has sat with applicants through every stage of this process.",
  credentials: "",
  avatar: null,
  avatar_alt: "",
  website: "",
  linkedin_url: "https://www.linkedin.com/in/example",
  x_url: "",
  is_public: true,
  show_in_directory: true,
  post_count: 2,
  has_public_page: true,
  created_at: "2026-07-01T09:00:00Z",
  updated_at: "2026-08-20T09:00:00Z",
};

/** One of each interesting state: flagged, clean, and an agency reply. */
export const adminComments = [
  {
    id: "c-1",
    post_title: blogPostCard.title,
    post_slug: blogPostCard.slug,
    author_name: "Ada Obi",
    email: "ada@example.com",
    website: "",
    body: "How long does a transcript usually take from a Nigerian polytechnic?",
    status: "pending" as const,
    flagged_reason: "",
    is_pinned: false,
    is_from_staff: false,
    parent: null,
    parent_body: "",
    moderated_by_name: "",
    moderated_at: null,
    ip_address: "102.89.0.1",
    created_at: "2026-08-21T08:30:00Z",
  },
  {
    id: "c-2",
    post_title: blogPostCard.title,
    post_slug: blogPostCard.slug,
    author_name: "Quick Visa Agent",
    email: "spam@example.com",
    website: "https://example.com",
    body: "We can get you a cheap visa fast, message https://a.example https://b.example",
    status: "pending" as const,
    flagged_reason: "3 links (limit 1); blocked phrase “cheap visa”",
    is_pinned: false,
    is_from_staff: false,
    parent: null,
    parent_body: "",
    moderated_by_name: "",
    moderated_at: null,
    ip_address: "10.0.0.9",
    created_at: "2026-08-21T09:10:00Z",
  },
  {
    id: "c-3",
    post_title: blogPostCard.title,
    post_slug: blogPostCard.slug,
    author_name: "Ngozi Eze",
    email: "",
    website: "",
    body: "It varies by institution, and nobody can promise a date — start it first.",
    status: "approved" as const,
    flagged_reason: "",
    is_pinned: true,
    is_from_staff: true,
    parent: "c-1",
    parent_body: "How long does a transcript usually take from a Nigerian polytechnic?",
    moderated_by_name: "Ngozi Eze",
    moderated_at: "2026-08-21T09:20:00Z",
    ip_address: null,
    created_at: "2026-08-21T09:20:00Z",
  },
];

export const commentSummaryCounts = { pending: 2, approved: 4, spam: 1, rejected: 0 };

// ---------------------------------------------------------------------------
// Pricing
// ---------------------------------------------------------------------------

/**
 * The public pricing response.
 *
 * The fee here is the one the fixture *charges*, so a test that reads the
 * checkout button and a test that reads the API are looking at the same number —
 * which is the whole point of the pricing layer.
 */
export const publicPricing = {
  access_fee: {
    amount: "5000.00",
    major_units: 5000,
    currency: "NGN",
    symbol: "₦",
    formatted: "₦5,000",
    ascii: "NGN 5,000",
    note: "Covers everything from the first shortlist to landing on campus.",
  },
  costs: [
    {
      id: "ce-1",
      label: "Proof of funds",
      amount: "₦2.5m to ₦4m, held for six months",
      note: "Held before the visa, not spent.",
      is_verified: true,
      display_order: 10,
    },
    {
      id: "ce-2",
      label: "Visa and health charges",
      // The stale state, which is the one worth exercising: the figure is
      // withheld and the label says so.
      amount: "Ask us — this changes",
      note: "Paid to the embassy, never to us.",
      is_verified: false,
      display_order: 20,
    },
  ],
  unverified_label: "Ask us — this changes",
};

export const adminPricing = {
  access_fee_amount: "5000.00",
  access_fee_currency: "NGN",
  access_fee_note: "Covers everything from the first shortlist to landing on campus.",
  estimate_stale_after_days: 120,
  formatted_access_fee: "₦5,000",
  ascii_access_fee: "NGN 5,000",
  currency_symbol: "₦",
  updated_at: "2026-09-01T09:00:00Z",
};

export const adminCostEstimates = [
  {
    id: "ce-1",
    label: "Proof of funds",
    amount_display: "₦2.5m to ₦4m, held for six months",
    note: "Held before the visa, not spent.",
    verified_on: "2026-09-01",
    verified_source: "Embassy guidance, checked by hand",
    display_order: 10,
    is_active: true,
    public_amount: "₦2.5m to ₦4m, held for six months",
    is_stale: false,
    created_at: "2026-07-01T09:00:00Z",
    updated_at: "2026-09-01T09:00:00Z",
  },
  {
    id: "ce-2",
    label: "Visa and health charges",
    amount_display: "₦180,000",
    note: "Paid to the embassy, never to us.",
    verified_on: "2025-01-04",
    verified_source: "",
    display_order: 20,
    is_active: true,
    public_amount: "Ask us — this changes",
    is_stale: true,
    created_at: "2026-07-01T09:00:00Z",
    updated_at: "2026-07-01T09:00:00Z",
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
  "apps.blog.serializers.PostListSerializer": Object.keys(blogPostCard),
  "apps.blog.serializers.PostDetailSerializer": Object.keys(blogPostDetail),
  "apps.blog.serializers.AdminPostSerializer": Object.keys(adminBlogPost),
  "apps.blog.serializers.CategorySerializer": Object.keys(blogCategories[0]),
  "apps.blog.serializers.TagSerializer": Object.keys(blogTags[0]),
  "apps.blog.serializers.PostRevisionSerializer": Object.keys(blogRevisions[0]),
  "apps.blog.serializers.BlogSettingsSerializer": Object.keys(blogSettings),
  "apps.blog.serializers.AuthorProfileSerializer": Object.keys(authorProfile),
  "apps.blog.serializers.AdminCommentSerializer": Object.keys(adminComments[0]),
  "apps.blog.serializers.PostFaqSerializer": Object.keys(postFaqs[0]),
  "apps.payments.pricing_api.PricingSerializer": Object.keys(adminPricing),
  "apps.payments.pricing_api.AdminCostEstimateSerializer": Object.keys(adminCostEstimates[0]),
  "apps.payments.pricing_api.CostEstimateSerializer": Object.keys(publicPricing.costs[0]),
} as const;
