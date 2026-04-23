from django.conf import settings
from django.http import HttpResponse


def robots_txt(request):
    return HttpResponse(
        "\n".join(
            [
                "User-agent: *",
                "Allow: /",
                "Disallow: /admin/",
                "Disallow: /api/",
                f"Sitemap: {settings.SITE_URL}/sitemap.xml",
            ]
        ),
        content_type="text/plain",
    )
