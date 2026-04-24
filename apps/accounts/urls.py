from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AddressViewSet, LoginView, MeView, RegisterView, TokenRefreshCookieView, logout_view

router = DefaultRouter()
router.register("addresses", AddressViewSet, basename="address")

urlpatterns = [
    path("register/", RegisterView.as_view(), name="api-register"),
    path("login/", LoginView.as_view(), name="api-login"),
    path("logout/", logout_view, name="api-logout"),
    path("me/", MeView.as_view(), name="api-me"),
    path("token/refresh/", TokenRefreshCookieView.as_view(), name="token-refresh"),
    path("", include(router.urls)),
]
