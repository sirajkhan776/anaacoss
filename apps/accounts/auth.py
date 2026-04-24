from django.conf import settings


def _cookie_options(max_age):
    return {
        "max_age": max_age,
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "path": "/",
    }


def set_auth_cookies(response, access=None, refresh=None):
    if access is not None:
        response.set_cookie(
            settings.AUTH_ACCESS_COOKIE_NAME,
            access,
            **_cookie_options(int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())),
        )
    if refresh is not None:
        response.set_cookie(
            settings.AUTH_REFRESH_COOKIE_NAME,
            refresh,
            **_cookie_options(int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())),
        )
    return response


def clear_auth_cookies(response):
    response._clear_auth_cookies = True
    response.delete_cookie(settings.AUTH_ACCESS_COOKIE_NAME, path="/", samesite=settings.AUTH_COOKIE_SAMESITE)
    response.delete_cookie(settings.AUTH_REFRESH_COOKIE_NAME, path="/", samesite=settings.AUTH_COOKIE_SAMESITE)
    return response
