from django.db.models import Q
from django.shortcuts import get_object_or_404, render
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


def home(request):
    ctx = base_context()
    ctx.update(
        {
            "featured_categories": Category.objects.filter(is_featured=True)[:6],
            "trending_products": Product.objects.visible().filter(is_trending=True).prefetch_related("images")[:8],
            "best_sellers": Product.objects.visible().filter(is_best_seller=True).prefetch_related("images")[:8],
            "new_arrivals": Product.objects.visible().filter(is_new_arrival=True).prefetch_related("images")[:8],
            "hero_banners": Banner.objects.filter(is_active=True, placement="hero")[:3],
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
            qs = qs.filter(Q(category__slug=category) | Q(category__parent__slug=category))
        if brand := params.get("brand"):
            qs = qs.filter(brand__slug=brand)
        if skin_type := params.get("skin_type"):
            qs = qs.filter(skin_type=skin_type)
        if params.get("offer") == "true":
            qs = qs.filter(is_offer=True)
        if min_price := params.get("min_price"):
            qs = qs.filter(price__gte=min_price)
        if max_price := params.get("max_price"):
            qs = qs.filter(price__lte=max_price)
        if rating := params.get("rating"):
            qs = qs.filter(rating__gte=rating)
        sort = params.get("sort")
        if sort in {"price", "-price", "rating", "-rating", "created_at", "-created_at"}:
            qs = qs.order_by(sort)
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
