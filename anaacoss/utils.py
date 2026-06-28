from urllib.parse import urljoin

from django.conf import settings


def absolute_media_url(url, request=None):
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    if request is not None:
        return request.build_absolute_uri(url)
    return urljoin(f"{settings.SITE_URL}/", url.lstrip("/"))
