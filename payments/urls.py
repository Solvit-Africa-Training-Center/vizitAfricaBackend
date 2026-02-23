# payments/urls.py
from django.urls import path
from .views import (
    CreatePaymentIntentView,
    ConfirmPaymentView,
    StripeWebhookView,
    RefundPaymentView,
)

urlpatterns = [
    path("stripe/create-intent/", CreatePaymentIntentView.as_view(), name="create-payment-intent"),
    path("stripe/confirm/", ConfirmPaymentView.as_view(), name="confirm-payment"),
    path("stripe/refund/", RefundPaymentView.as_view(), name="refund-payment"),
    path("stripe/webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
]
