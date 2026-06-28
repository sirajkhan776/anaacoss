from django.test import RequestFactory, TestCase, override_settings

from .models import Banner
from .serializers import BannerSerializer


@override_settings(ALLOWED_HOSTS=["anaacoss.onrender.com", "testserver", "localhost"])
class BannerSerializerTests(TestCase):
    def test_banner_serializer_returns_absolute_uploaded_image_url(self):
        banner = Banner.objects.create(
            title="Hero banner",
            image="banners/hero.jpg",
            placement="hero",
        )
        request = RequestFactory().get("/api/banners/")
        request.META["HTTP_HOST"] = "anaacoss.onrender.com"
        request.META["wsgi.url_scheme"] = "https"

        data = BannerSerializer(banner, context={"request": request}).data

        self.assertEqual(data["image_url"], "https://anaacoss.onrender.com/media/banners/hero.jpg")
