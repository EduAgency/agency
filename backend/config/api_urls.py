"""
The API surface.

Split into three bands, each with its own permission posture:

* ``/api/auth/``   — public or self-service account endpoints
* ``/api/``        — student-facing; a student only ever sees their own records
* ``/api/admin/``  — staff, each route gated on a named AdminProfile permission
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from apps.accounts import views as accounts_views
from apps.applications import views as application_views
from apps.forms_engine import views as form_views
from apps.notifications import api as notification_views
from apps.payments import api as payment_views
from apps.referrals import views as referral_views
from apps.schools import views as school_views

# --- student-facing ---------------------------------------------------------
router = DefaultRouter()
router.register("applications", application_views.ApplicationViewSet, basename="application")
router.register("checklist-items", application_views.ChecklistItemViewSet, basename="checklist-item")
router.register("documents", application_views.StudentDocumentViewSet, basename="document")
router.register("schools", school_views.SchoolViewSet, basename="school")
router.register("programmes", school_views.ProgrammeViewSet, basename="programme")
router.register("countries", school_views.CountryViewSet, basename="country")
router.register("requirement-categories", school_views.RequirementCategoryViewSet, basename="requirement-category")

# --- staff ------------------------------------------------------------------
admin_router = DefaultRouter()
admin_router.register("students", accounts_views.AdminStudentViewSet, basename="admin-student")
admin_router.register("forms", form_views.AdminFormViewSet, basename="admin-form")
admin_router.register("submissions", form_views.AdminSubmissionViewSet, basename="admin-submission")
admin_router.register("requirement-sets", school_views.RequirementSetViewSet, basename="admin-requirement-set")
admin_router.register("requirement-items", school_views.RequirementItemViewSet, basename="admin-requirement-item")
admin_router.register("review-queue", application_views.ReviewQueueViewSet, basename="review-queue")
admin_router.register("payments", payment_views.AdminPaymentViewSet, basename="admin-payment")
admin_router.register("gateway-configs", payment_views.AdminGatewayConfigViewSet, basename="admin-gateway-config")
admin_router.register("webhook-events", payment_views.AdminWebhookEventViewSet, basename="admin-webhook-event")
admin_router.register("reconciliation", payment_views.AdminReconciliationViewSet, basename="admin-reconciliation")
admin_router.register("referral-codes", referral_views.AdminReferralCodeViewSet, basename="admin-referral-code")
admin_router.register("reward-rules", referral_views.AdminRewardRuleViewSet, basename="admin-reward-rule")
admin_router.register("rewards", referral_views.AdminRewardViewSet, basename="admin-reward")
admin_router.register("payouts", referral_views.AdminPayoutViewSet, basename="admin-payout")

auth_patterns = [
    path("signup/", accounts_views.SignupView.as_view(), name="signup"),
    path("login/", accounts_views.LoginView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token-verify"),
    path("verify-email/", accounts_views.VerifyEmailView.as_view(), name="verify-email"),
    path("resend-verification/", accounts_views.ResendVerificationView.as_view(), name="resend-verification"),
    path("password/reset/", accounts_views.PasswordResetRequestView.as_view(), name="password-reset"),
    path("password/reset/confirm/", accounts_views.PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("password/change/", accounts_views.PasswordChangeView.as_view(), name="password-change"),

    # Two-factor authentication.
    path("mfa/", accounts_views.MfaStatusView.as_view(), name="mfa-status"),
    path("mfa/enrol/", accounts_views.MfaEnrolView.as_view(), name="mfa-enrol"),
    path("mfa/confirm/", accounts_views.MfaConfirmView.as_view(), name="mfa-confirm"),
    path("mfa/recovery-codes/", accounts_views.MfaRecoveryCodesView.as_view(), name="mfa-recovery-codes"),
    path("mfa/disable/", accounts_views.MfaDisableView.as_view(), name="mfa-disable"),
    path("me/", accounts_views.MeView.as_view(), name="me"),
]

urlpatterns = [
    path("auth/", include((auth_patterns, "auth"))),

    # Telegram posts here. The secret path segment is checked against the
    # configured verify token — Telegram carries no credentials of ours.
    path(
        "webhooks/telegram/<str:secret>/",
        notification_views.TelegramWebhookView.as_view(),
        name="telegram-webhook",
    ),
    path("profile/", accounts_views.StudentProfileView.as_view(), name="student-profile"),

    # Forms — one route serves every admin-built form, by slug.
    path("forms/<slug:slug>/", form_views.LiveFormView.as_view(), name="live-form"),
    path("forms/<slug:slug>/submit/", form_views.SubmitFormView.as_view(), name="submit-form"),
    path("my/submissions/", form_views.MySubmissionsView.as_view(), name="my-submissions"),

    # Payments
    path("payments/gateways/", payment_views.GatewayOptionsView.as_view(), name="gateway-options"),
    path("payments/initiate/", payment_views.InitiatePaymentView.as_view(), name="initiate-payment"),
    path("payments/verify/", payment_views.VerifyPaymentView.as_view(), name="verify-payment"),
    path("payments/mine/", payment_views.MyPaymentsView.as_view(), name="my-payments"),

    # Notifications — the preference centre, channel connection, and the inbox.
    path("notifications/", notification_views.InboxView.as_view(), name="inbox"),
    path("notifications/preferences/", notification_views.NotificationPreferencesView.as_view(), name="notification-preferences"),
    path("notifications/quiet-hours/", notification_views.QuietHoursView.as_view(), name="quiet-hours"),
    path("notifications/whatsapp/", notification_views.WhatsAppOptInView.as_view(), name="whatsapp-opt-in"),
    path("notifications/telegram/", notification_views.TelegramLinkView.as_view(), name="telegram-link"),

    # Referrals
    path("referrals/check/", referral_views.CheckReferralCodeView.as_view(), name="check-referral"),
    path("referrals/mine/", referral_views.MyReferralsView.as_view(), name="my-referrals"),
    path("referrals/payout/", referral_views.RequestPayoutView.as_view(), name="request-payout"),

    path("", include(router.urls)),
    path("admin/", include(admin_router.urls)),
]
