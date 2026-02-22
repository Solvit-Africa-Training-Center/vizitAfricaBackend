# payments/urls.py
from django.urls import path
from .views import (
    CashInView,
    CashOutView,
    CreatePaymentIntentView,
    ConfirmPaymentView,
    StripeWebhookView,
    RefundPaymentView,
)

urlpatterns = [
    path("cashin/", CashInView.as_view(), name="cashin"),
    path("cashout/", CashOutView.as_view(), name="cashout"),
    path("stripe/create-intent/", CreatePaymentIntentView.as_view(), name="create-payment-intent"),
    path("stripe/confirm/", ConfirmPaymentView.as_view(), name="confirm-payment"),
    path("stripe/refund/", RefundPaymentView.as_view(), name="refund-payment"),
    path("stripe/webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
]
