from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.views import GoogleLoginView


from accounts.views import UserViewSet, LoginViewSet, SavedItemViewSet, ContactView

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="users")
router.register(r"saved-items", SavedItemViewSet, basename="saved-items")

urlpatterns = [
    path("", include(router.urls)),

    # JWT auth (DO NOT use router)
    path("login/", LoginViewSet.as_view(), name="login"),
    path("login/google/", GoogleLoginView.as_view(), name="google-login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("contact/", ContactView.as_view(), name="contact"),
]
