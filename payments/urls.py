# payments/urls.py
from django.urls import path
from .views import CashInView, CashOutView

urlpatterns = [
    path("cashin/", CashInView.as_view(), name="cashin"),
    path("cashout/", CashOutView.as_view(), name="cashout"),
]
