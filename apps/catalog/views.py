from django.db.models import Q
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.content.models import Banner, Testimonial

from .models import Brand, Category, Product, Review
from .serializers import BrandSerializer, CategorySerializer, ProductCardSerializer, ProductDetailSerializer, ReviewSerializer


def base_context():
    return {
        "categories": Category.objects.filter(parent__isnull=True),
    }


def banner_media_type(banner):
    remote_url = (banner.remote_url or "").lower().split("?", 1)[0]
    if remote_url.endswith((".mp4", ".webm", ".ogg", ".mov", ".m4v")):
        return "video"
    return "image"


def home(request):
    hero_banners = Banner.objects.filter(is_active=True, placement="hero")[:3]
    home_feed = Product.objects.visible().select_related("brand", "category").prefetch_related("images")
    ctx = base_context()
    ctx.update(
        {
            "featured_categories": Category.objects.filter(is_featured=True)[:6],
            "trending_products": Product.objects.visible().filter(is_trending=True).prefetch_related("images")[:8],
            "best_sellers": Product.objects.visible().filter(is_best_seller=True).prefetch_related("images")[:8],
            "home_products": home_feed[:12],
            "home_feed_count": home_feed.count(),
            "new_arrivals": Product.objects.visible().filter(is_new_arrival=True).prefetch_related("images")[:8],
            "home_categories": Category.objects.filter(parent__isnull=True),
            "home_brands": Brand.objects.order_by("name"),
            "hero_banners": hero_banners,
            "mobile_hero_slides": [
                {
                    "eyebrow": banner.eyebrow or "New luminous ritual collection",
                    "title": banner.title or "Anaacoss",
                    "subtitle": banner.subtitle or "Premium skincare, makeup, fragrance, and tools curated for polished everyday radiance.",
                    "cta_label": banner.cta_label or "Shop the edit",
                    "cta_url": banner.cta_url or "/shop/",
                    "media_type": banner_media_type(banner),
                    "media_url": banner.remote_url if banner_media_type(banner) == "video" else banner.image_url,
                }
                for banner in hero_banners
                if (banner.remote_url if banner_media_type(banner) == "video" else banner.image_url)
            ],
            "offer_banners": Banner.objects.filter(is_active=True, placement="offer")[:3],
            "testimonials": Testimonial.objects.filter(is_active=True)[:6],
        }
    )
    return render(request, "home.html", ctx)


def shop(request, category_slug=None):
    ctx = base_context()
    products = Product.objects.visible().select_related("brand", "category").prefetch_related("images")
    category = None
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(Q(category=category) | Q(category__parent=category))
    ctx.update(
        {
            "products": products[:24],
            "active_category": category,
            "brands": Brand.objects.all(),
            "page_title": category.name if category else "Shop",
        }
    )
    return render(request, "catalog/shop.html", ctx)


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.visible().select_related("brand", "category").prefetch_related("images", "variants", "reviews__images", "reviews__user"),
        slug=slug,
    )
    related = (
        Product.objects.visible()
        .filter(category=product.category)
        .exclude(id=product.id)
        .select_related("brand", "category")
        .prefetch_related("images")[:4]
    )
    ctx = base_context()
    ctx.update({"product": product, "related_products": related})
    return render(request, "catalog/product_detail.html", ctx)


def product_review_page(request, slug):
    product = get_object_or_404(
        Product.objects.visible().select_related("brand", "category").prefetch_related("images", "reviews__images", "reviews__user"),
        slug=slug,
    )
    existing_review = None
    if request.user.is_authenticated:
        existing_review = product.reviews.filter(user=request.user).prefetch_related("images").first()
    ctx = base_context()
    ctx.update(
        {
            "product": product,
            "existing_review": existing_review,
            "checkout_mode": True,
            "hide_header_search": True,
            "page_title": "Write Review" if not existing_review else "Your Review",
            "product_page_url": reverse("storefront-product-detail", kwargs={"slug": product.slug}),
        }
    )
    return render(request, "catalog/review_form.html", ctx)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = "slug"


class BrandViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    lookup_field = "slug"


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductCardSerializer
    lookup_field = "slug"

    def get_queryset(self):
        qs = Product.objects.visible().select_related("brand", "category").prefetch_related("images")
        params = self.request.query_params
        if q := params.get("q"):
            qs = qs.filter(Q(name__icontains=q) | Q(short_description__icontains=q) | Q(brand__name__icontains=q))
        if category := params.get("category"):
            category_values = [item.strip() for item in category.split(",") if item.strip()]
            if category_values:
                category_query = Q()
                for category_slug in category_values:
                    category_query |= Q(category__slug=category_slug) | Q(category__parent__slug=category_slug)
                qs = qs.filter(category_query)
        if gender := params.get("gender"):
            qs = qs.filter(gender=gender)
        if brand := params.get("brand"):
            brand_values = [item.strip() for item in brand.split(",") if item.strip()]
            if brand_values:
                qs = qs.filter(brand__slug__in=brand_values)
        if skin_type := params.get("skin_type"):
            qs = qs.filter(skin_type=skin_type)
        if params.get("offer") == "true":
            qs = qs.filter(is_offer=True)
        if params.get("availability") == "in_stock":
            qs = qs.filter(stock__gt=0)
        if min_price := params.get("min_price"):
            qs = qs.filter(price__gte=min_price)
        if max_price := params.get("max_price"):
            qs = qs.filter(price__lte=max_price)
        if rating := params.get("rating"):
            qs = qs.filter(rating__gte=rating)
        sort = params.get("sort")
        sort_map = {
            "price_low": "price",
            "price_high": "-price",
            "newest": "-created_at",
            "popular": "-review_count",
            "name": Lower("name"),
        }
        if sort in {"price", "-price", "rating", "-rating", "created_at", "-created_at"}:
            qs = qs.order_by(sort)
        elif sort in sort_map:
            mapped = sort_map[sort]
            if sort == "name":
                qs = qs.order_by(mapped)
            elif sort == "popular":
                qs = qs.order_by("-review_count", "-rating", "-created_at")
            else:
                qs = qs.order_by(mapped)
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProductDetailSerializer
        return ProductCardSerializer

    @action(detail=False)
    def suggestions(self, request):
        q = request.query_params.get("q", "")
        products = self.get_queryset().filter(name__icontains=q)[:6] if q else []
        return Response(ProductCardSerializer(products, many=True, context={"request": request}).data)

    @action(detail=False)
    def curated(self, request):
        return Response(
            {
                "trending": ProductCardSerializer(Product.objects.visible().filter(is_trending=True)[:8], many=True).data,
                "best_sellers": ProductCardSerializer(Product.objects.visible().filter(is_best_seller=True)[:8], many=True).data,
                "new_arrivals": ProductCardSerializer(Product.objects.visible().filter(is_new_arrival=True)[:8], many=True).data,
            }
        )


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = Review.objects.select_related("user", "product").prefetch_related("images")
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return qs
        return qs.filter(is_approved=True)

    def perform_create(self, serializer):
        if self.request.user.is_staff:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Only customer accounts can submit product reviews.")
        serializer.save()

    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You can edit only your own review.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You can delete only your own review.")
        instance.delete()
