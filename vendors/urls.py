# vendors/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VendorViewSet

router = DefaultRouter()
router.register('', VendorViewSet, basename='vendor')

urlpatterns = [
    path('', include(router.urls)),
    path('requests/<pk>/confirm/', VendorViewSet.as_view({'post': 'confirm_item'}), name='vendor-confirm-item'),
]
