# payments/urls.py
from django.urls import path
from .views import payload, CashOutView

urlpatterns = [
    path("cashin/", payload.as_view(), name="cashin"),
    path("cashout/", CashOutView.as_view(), name="cashout"),
]
