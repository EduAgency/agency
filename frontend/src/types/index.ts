export * from "./forms";

export type ChecklistItemStatus =
  | "not_started"
  | "in_progress"
  | "uploaded"
  | "pending_review"
  | "verified"
  | "rejected"
  | "waived"
  | "not_applicable";

export interface ChecklistItem {
  id: string;
  label: string;
  description: string;
  help_text: string;
  category_name: string;
  category_slug: string;
  is_required: boolean;
  priority: "high" | "medium" | "low";
  evidence_type: "document" | "form" | "document_and_form" | "task" | "external";
  accepted_file_types: string[];
  max_file_size_mb: number;
  status: ChecklistItemStatus;
  /** Always present when status is "rejected" — the backend refuses a rejection without one. */
  rejection_reason: string;
  due_date: string | null;
  document_id: string | null;
  updated_at: string;
}

export interface CategoryProgress {
  category: string;
  slug: string;
  total: number;
  verified: number;
  uploaded: number;
  percent: number;
}

export interface Checklist {
  id: string;
  /** Which number the progress bar shows. "verified" is the honest default. */
  progress_basis: "verified" | "uploaded";
  percent_complete: number;
  percent_uploaded: number;
  required_count: number;
  verified_count: number;
  uploaded_count: number;
  source_version: number;
  items: ChecklistItem[];
  categories: CategoryProgress[];
}

export interface Application {
  id: string;
  school: { id: string; name: string; country: string | null; logo: string | null };
  programme: { id: string; name: string } | null;
  intake: string;
  status: string;
  status_display: string;
  target_submission_date: string | null;
  checklist: Pick<Checklist, "percent_complete" | "percent_uploaded" | "required_count" | "verified_count"> | null;
}

export interface StudentProfile {
  id: string;
  email: string;
  full_name: string;
  stage: string;
  has_platform_access: boolean;
  access_granted_at: string | null;
}

export type PaymentStatus =
  | "pending"
  | "processing"
  | "successful"
  | "failed"
  | "abandoned"
  | "reversed"
  | "refunded"
  | "partially_refunded";

export interface Payment {
  id: string;
  reference: string;
  gateway: string;
  amount: string;
  currency: string;
  purpose: string;
  status: PaymentStatus;
  paid_at: string | null;
  created_at: string;
}

export interface GatewayOption {
  gateway: "paystack" | "flutterwave";
  label: string;
  currency: string;
  is_test_mode: boolean;
}

export interface ReferralSummary {
  code: string;
  share_url: string;
  signups: number;
  conversions: number;
  total_earned: string;
  available_balance: string;
  currency: string;
}
