from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("webhooks/paystack/", views.paystack_webhook, name="paystack-webhook"),
    path("webhooks/flutterwave/", views.flutterwave_webhook, name="flutterwave-webhook"),
]
