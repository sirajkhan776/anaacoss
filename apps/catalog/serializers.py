from django.db import transaction
from rest_framework import serializers

from .models import Brand, Category, Product, ProductImage, ProductVariant, Review, ReviewImage


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description", "icon", "is_featured")


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ("id", "name", "slug", "story", "is_premium")


class ProductImageSerializer(serializers.ModelSerializer):
    url = serializers.ReadOnlyField()
    thumbnail = serializers.ReadOnlyField()

    class Meta:
        model = ProductImage
        fields = ("id", "media_type", "placement", "url", "thumbnail", "alt_text", "is_primary", "sort_order")


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ("id", "name", "value", "price_delta", "stock", "sku")


class ProductCardSerializer(serializers.ModelSerializer):
    brand = BrandSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    primary_image = serializers.SerializerMethodField()
    secondary_image = serializers.SerializerMethodField()
    final_price = serializers.ReadOnlyField()
    in_stock = serializers.ReadOnlyField()
    discount_percent = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "brand",
            "category",
            "gender",
            "short_description",
            "price",
            "discount_price",
            "final_price",
            "discount_percent",
            "badge",
            "rating",
            "review_count",
            "stock",
            "in_stock",
            "primary_image",
            "secondary_image",
        )

    def get_primary_image(self, obj):
        image = obj.images.filter(media_type="image", placement="gallery", is_primary=True).first() or obj.images.filter(media_type="image").first()
        return image.url if image else ""

    def get_secondary_image(self, obj):
        image = obj.images.filter(media_type="image", placement="gallery").exclude(is_primary=True).first()
        return image.url if image else self.get_primary_image(obj)


class ProductDetailSerializer(ProductCardSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta(ProductCardSerializer.Meta):
        fields = ProductCardSerializer.Meta.fields + (
            "description",
            "ingredients",
            "how_to_use",
            "skin_type",
            "gender",
            "product_type",
            "is_offer",
            "images",
            "variants",
        )


class ReviewImageSerializer(serializers.ModelSerializer):
    url = serializers.ImageField(source="image", read_only=True)

    class Meta:
        model = ReviewImage
        fields = ("id", "url", "alt_text")


class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    images = ReviewImageSerializer(many=True, read_only=True)

    class Meta:
        model = Review
        fields = ("id", "product", "user_name", "rating", "title", "body", "images", "created_at")
        read_only_fields = ("user_name", "created_at")

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["user"] = request.user
        with transaction.atomic():
            review = super().create(validated_data)
            for image in request.FILES.getlist("images"):
                ReviewImage.objects.create(review=review, image=image, alt_text=f"{review.product.name} customer review")
        return review

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
