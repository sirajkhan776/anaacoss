from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from .auth import set_auth_cookies
from .authentication import CookieJWTAuthentication


class JWTUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.authenticator = CookieJWTAuthentication()

    def __call__(self, request):
        request.user = getattr(request, "user", AnonymousUser())
        request.auth = None
        request._jwt_cookie_tokens = {}

        user_auth = self._authenticate_request(request)
        if user_auth:
            request.user, request.auth = user_auth
        elif not getattr(request.user, "is_authenticated", False):
            request.user = AnonymousUser()

        response = self.get_response(request)
        if request._jwt_cookie_tokens and not getattr(response, "_clear_auth_cookies", False):
            set_auth_cookies(response, **request._jwt_cookie_tokens)
        return response

    def _authenticate_request(self, request):
        try:
            return self.authenticator.authenticate(request)
        except Exception:
            return self._refresh_from_cookie(request)

    def _refresh_from_cookie(self, request):
        refresh_value = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
        if not refresh_value:
            return None
        try:
            refresh = RefreshToken(refresh_value)
            access_value = str(refresh.access_token)
            validated = self.authenticator.get_validated_token(access_value)
            user = self.authenticator.get_user(validated)
        except (TokenError, Exception):
            return None
        request._jwt_cookie_tokens["access"] = access_value
        return user, validated
