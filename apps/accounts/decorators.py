from functools import wraps

from django.http import HttpResponse
from django.shortcuts import redirect


def jwt_required_page(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if getattr(request.user, "is_authenticated", False):
            return view_func(request, *args, **kwargs)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return HttpResponse("Authentication credentials were not provided.", status=401)
        return redirect("home")

    return _wrapped
