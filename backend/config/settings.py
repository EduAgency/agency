"""
Django settings for the Nasuru agency platform.

Environment-driven (django-environ) so the same image runs in dev, staging and
production. Never put real secrets in this file — they belong in the env.
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:3000"]),
    USE_S3=(bool, False),
    SENTRY_DSN=(str, ""),
    ENVIRONMENT=(str, "local"),
)
environ.Env.read_env(BASE_DIR / ".env")

ENVIRONMENT = env("ENVIRONMENT")  # local | staging | production
DEBUG = env("DJANGO_DEBUG")
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-insecure-key-change-me")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# Fernet key used to encrypt payment gateway credentials at rest (plan §5.1).
# Generate with:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")

# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "django_celery_beat",
    "django_celery_results",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.schools",
    "apps.forms_engine",
    "apps.applications",
    "apps.payments",
    "apps.referrals",
    "apps.notifications",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # OTP middleware must sit after auth: it gates the Django admin behind TOTP.
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.AuditContextMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://nasuru:nasuru@localhost:5432/nasuru",
    )
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

# --------------------------------------------------------------------------
# Auth / passwords
# --------------------------------------------------------------------------
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.EmailBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# I18N — Nigeria-based operation
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

DEFAULT_CURRENCY = "NGN"

# --------------------------------------------------------------------------
# Static & media
# --------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

if env("USE_S3"):
    # Student documents (passports, transcripts) never live on local disk in
    # a deployed environment — plan §2.1.
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("AWS_STORAGE_BUCKET_NAME"),
            "region_name": env("AWS_S3_REGION_NAME", default="eu-west-1"),
            "endpoint_url": env("AWS_S3_ENDPOINT_URL", default=None),
            "access_key": env("AWS_ACCESS_KEY_ID", default=None),
            "secret_key": env("AWS_SECRET_ACCESS_KEY", default=None),
            "default_acl": "private",
            "querystring_auth": True,
            "querystring_expire": 900,  # signed URLs expire in 15 minutes
            "file_overwrite": False,
        },
    }

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
MAX_DOCUMENT_UPLOAD_BYTES = env.int("MAX_DOCUMENT_UPLOAD_BYTES", default=20 * 1024 * 1024)

# --------------------------------------------------------------------------
# DRF
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "signup": "5/hour",
        "login": "10/hour",
        "password_reset": "5/hour",
        "upload": "60/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Nasuru Agency Platform API",
    "DESCRIPTION": "Student recruitment platform — forms, checklists, payments, referrals.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    # Several models have a "status" or "purpose" field with different choices.
    # Naming them explicitly keeps the generated client's types readable
    # instead of "Status399Enum".
    "ENUM_NAME_OVERRIDES": {
        "PaymentStatusEnum": "apps.payments.models.PAYMENT_STATUS_CHOICES",
        "PaymentPurposeEnum": "apps.payments.models.PAYMENT_PURPOSE_CHOICES",
        "GatewayEnum": "apps.payments.models.GATEWAY_CHOICES",
        "RefundStatusEnum": "apps.payments.models.REFUND_STATUS_CHOICES",
        "WebhookStatusEnum": "apps.payments.models.WEBHOOK_STATUS_CHOICES",
        "ApplicationStatusEnum": "apps.applications.models.APPLICATION_STATUS_CHOICES",
        "ChecklistItemStatusEnum": "apps.applications.models.CHECKLIST_ITEM_STATUS_CHOICES",
        "DocumentUploadStatusEnum": "apps.applications.models.DOCUMENT_UPLOAD_STATUS_CHOICES",
        # Forms and requirement sets share one draft/published/archived
        # lifecycle by design, so they share one enum name.
        "PublishStatusEnum": "apps.forms_engine.models.FORM_STATUS_CHOICES",
        "FormAudienceEnum": "apps.forms_engine.models.FORM_AUDIENCE_CHOICES",
        "FormPurposeEnum": "apps.forms_engine.models.FORM_PURPOSE_CHOICES",
        "SubmissionStatusEnum": "apps.forms_engine.models.SUBMISSION_STATUS_CHOICES",
        "ReferralPayoutStatusEnum": "apps.referrals.models.REFERRAL_PAYOUT_STATUS_CHOICES",
        "ReferralRewardStatusEnum": "apps.referrals.models.REFERRAL_REWARD_STATUS_CHOICES",
        "ReferralTriggerEnum": "apps.referrals.models.REFERRAL_TRIGGER_CHOICES",
        "ReferralOwnerTypeEnum": "apps.referrals.models.REFERRAL_OWNER_TYPE_CHOICES",
        "UserRoleEnum": "apps.accounts.models.USER_ROLE_CHOICES",
        "StudentStageEnum": "apps.accounts.models.STUDENT_STAGE_CHOICES",
        "StudentSourceEnum": "apps.accounts.models.STUDENT_SOURCE_CHOICES",
        "RequirementEvidenceEnum": "apps.schools.models.REQUIREMENT_EVIDENCE_CHOICES",
        "RequirementPriorityEnum": "apps.schools.models.REQUIREMENT_PRIORITY_CHOICES",
        "SchoolKindEnum": "apps.schools.models.SCHOOL_KIND_CHOICES",
        "ProgrammeLevelEnum": "apps.schools.models.PROGRAMME_LEVEL_CHOICES",
        "NotificationStatusEnum": "apps.notifications.models.NOTIFICATION_STATUS_CHOICES",
        "NotificationCategoryEnum": "apps.notifications.models.NOTIFICATION_CATEGORY_CHOICES",
        "NotificationChannelEnum": "apps.notifications.models.NOTIFICATION_CHANNEL_CHOICES",
    },
}

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# --------------------------------------------------------------------------
# Celery
# --------------------------------------------------------------------------
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "django-cache"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 10 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 9 * 60
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TIMEZONE = TIME_ZONE

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/1"),
    }
}

# --------------------------------------------------------------------------
# Email / SMS
# --------------------------------------------------------------------------
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Nasuru <no-reply@nasuru.com>")
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:3000")

# --------------------------------------------------------------------------
# Payments (plan §5) — keys themselves live in PaymentGatewayConfig, encrypted.
# --------------------------------------------------------------------------
PAYSTACK_WEBHOOK_IP_ALLOWLIST = [
    "52.31.139.75",
    "52.49.173.169",
    "52.214.14.220",
]
ACCESS_FEE_AMOUNT = env.str("ACCESS_FEE_AMOUNT", default="5000.00")
ACCESS_FEE_CURRENCY = env.str("ACCESS_FEE_CURRENCY", default="NGN")

# --------------------------------------------------------------------------
# Security
# --------------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

if env("SENTRY_DSN"):
    import sentry_sdk

    sentry_sdk.init(
        dsn=env("SENTRY_DSN"),
        environment=ENVIRONMENT,
        traces_sample_rate=0.1,
        send_default_pii=False,  # never ship student PII to Sentry (NDPR, §10)
    )

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "apps": {"level": env("LOG_LEVEL", default="INFO"), "handlers": ["console"], "propagate": False},
    },
}
