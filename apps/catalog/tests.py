from django.test import RequestFactory, TestCase, override_settings
from django.core.management import call_command

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


class MergeSeedBrandsCommandTests(TestCase):
    def test_merges_case_variant_brands_into_uppercase_canonical_name(self):
        category = Category.objects.create(name="Body Care", slug="body-care")
        canonical_brand = Brand.objects.create(name="Bioaqua", slug="bioaqua")
        duplicate_brand = Brand.objects.create(
            name="BIOAQUA HERBAL BODY WHITENING",
            slug="bioaqua-herbal-body-whitening",
        )
        product = Product.objects.create(
            name="Body Whitening Soap",
            slug="body-whitening-soap",
            brand=duplicate_brand,
            category=category,
            short_description="Soap",
            description="Soap",
            price="50.00",
            sku="SKU-2",
            stock=10,
        )

        call_command("merge_seed_brands")

        brands = list(Brand.objects.order_by("name"))
        self.assertEqual(len(brands), 1)
        self.assertEqual(brands[0].name, "BIOAQUA")
        product.refresh_from_db()
        self.assertEqual(product.brand_id, brands[0].pk)
        self.assertFalse(Brand.objects.filter(pk=duplicate_brand.pk).exists())
