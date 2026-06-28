from django.test import RequestFactory, TestCase, override_settings

from .models import Brand, Category, Product, ProductImage
from .serializers import ProductCardSerializer, ProductImageSerializer


@override_settings(ALLOWED_HOSTS=["anaacoss.onrender.com", "testserver", "localhost"])
class ProductImageSerializerTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.category = Category.objects.create(name="Skincare", slug="skincare")
        self.brand = Brand.objects.create(name="Anaacoss Atelier", slug="anaacoss-atelier")
        self.product = Product.objects.create(
            name="Lumiere Cream",
            slug="lumiere-cream",
            brand=self.brand,
            category=self.category,
            short_description="Hydrating cream",
            description="Hydrating cream",
            price="100.00",
            sku="SKU-1",
            stock=5,
        )

    def test_product_card_serializer_returns_absolute_uploaded_image_url(self):
        ProductImage.objects.create(
            product=self.product,
            media_type=ProductImage.IMAGE,
            placement=ProductImage.GALLERY,
            image="products/lumiere.jpg",
            is_primary=True,
        )

        request = self.factory.get("/api/products/")
        request.META["HTTP_HOST"] = "anaacoss.onrender.com"
        request.META["wsgi.url_scheme"] = "https"

        data = ProductCardSerializer(self.product, context={"request": request}).data

        self.assertEqual(data["primary_image"], "https://anaacoss.onrender.com/media/products/lumiere.jpg")

    def test_product_image_serializer_returns_absolute_thumbnail_and_url(self):
        image = ProductImage.objects.create(
            product=self.product,
            media_type=ProductImage.IMAGE,
            placement=ProductImage.GALLERY,
            image="products/lumiere.jpg",
            is_primary=True,
        )

        request = self.factory.get("/api/products/lumiere-cream/")
        request.META["HTTP_HOST"] = "anaacoss.onrender.com"
        request.META["wsgi.url_scheme"] = "https"

        data = ProductImageSerializer(image, context={"request": request}).data

        self.assertEqual(data["url"], "https://anaacoss.onrender.com/media/products/lumiere.jpg")
        self.assertEqual(data["thumbnail"], "https://anaacoss.onrender.com/media/products/lumiere.jpg")
