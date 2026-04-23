from django.shortcuts import render
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.catalog.models import Product, ProductVariant
from apps.catalog.views import base_context

from .models import Coupon, Order, WishlistItem
from .serializers import CartSerializer, CouponSerializer, OrderSerializer, WishlistItemSerializer
from .services import get_cart, place_order


def cart_page(request):
    ctx = base_context()
    ctx["cart"] = get_cart(request)
    return render(request, "commerce/cart.html", ctx)


def checkout_page(request):
    ctx = base_context()
    ctx["cart"] = get_cart(request)
    return render(request, "commerce/checkout.html", ctx)


def wishlist_page(request):
    ctx = base_context()
    ctx["wishlist_items"] = request.user.wishlist_items.select_related("product").prefetch_related("product__images") if request.user.is_authenticated else []
    return render(request, "commerce/wishlist.html", ctx)


def offers_page(request):
    ctx = base_context()
    ctx["coupons"] = Coupon.objects.filter(is_active=True)
    ctx["offers"] = Product.objects.visible().filter(is_offer=True).prefetch_related("images")[:12]
    return render(request, "commerce/offers.html", ctx)


def dashboard_page(request):
    ctx = base_context()
    ctx["orders"] = request.user.orders.prefetch_related("items")[:8] if request.user.is_authenticated else []
    return render(request, "account/dashboard.html", ctx)


@api_view(["GET"])
def cart_api(request):
    return Response(CartSerializer(get_cart(request)).data)


@api_view(["POST"])
def add_to_cart(request):
    cart = get_cart(request)
    product = Product.objects.get(pk=request.data.get("product_id"))
    variant = None
    if request.data.get("variant_id"):
        variant = ProductVariant.objects.get(pk=request.data["variant_id"], product=product)
    qty = max(1, int(request.data.get("quantity", 1)))
    item, created = cart.items.get_or_create(product=product, variant=variant, defaults={"quantity": qty})
    if not created:
        item.quantity += qty
        item.save(update_fields=["quantity"])
    return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
def cart_item_api(request, item_id):
    cart = get_cart(request)
    item = cart.items.get(id=item_id)
    if request.method == "DELETE":
        item.delete()
    else:
        item.quantity = max(1, int(request.data.get("quantity", item.quantity)))
        item.save(update_fields=["quantity"])
    return Response(CartSerializer(cart).data)


@api_view(["POST", "DELETE"])
def coupon_api(request):
    cart = get_cart(request)
    if request.method == "DELETE":
        cart.coupon = None
        cart.save(update_fields=["coupon"])
        return Response(CartSerializer(cart).data)
    code = request.data.get("code", "").strip().upper()
    try:
        coupon = Coupon.objects.get(code__iexact=code)
    except Coupon.DoesNotExist:
        return Response({"code": ["Coupon not found."]}, status=status.HTTP_400_BAD_REQUEST)
    if not coupon.is_valid_for(cart.subtotal):
        return Response({"code": ["Coupon is inactive, expired, or below minimum order value."]}, status=status.HTTP_400_BAD_REQUEST)
    cart.coupon = coupon
    cart.save(update_fields=["coupon"])
    return Response(CartSerializer(cart).data)


class WishlistViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WishlistItem.objects.filter(user=self.request.user).select_related("product").prefetch_related("product__images")

    @action(detail=False, methods=["post"])
    def toggle(self, request):
        product = Product.objects.get(pk=request.data.get("product_id"))
        item, created = WishlistItem.objects.get_or_create(user=request.user, product=product)
        if not created:
            item.delete()
        return Response({
            "wishlisted": created,
            "product_id": product.id,
            "count": WishlistItem.objects.filter(user=request.user).count(),
        })


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items")

    def create(self, request, *args, **kwargs):
        cart = get_cart(request)
        if not cart.items.exists():
            return Response({"cart": ["Your cart is empty."]}, status=status.HTTP_400_BAD_REQUEST)
        required = ["full_name", "email", "phone", "address_line1", "city", "state", "postal_code"]
        missing = [field for field in required if not request.data.get(field)]
        if missing:
            return Response({field: ["This field is required."] for field in missing}, status=status.HTTP_400_BAD_REQUEST)
        order = place_order(request.user, cart, request.data)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class CouponViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Coupon.objects.filter(is_active=True)
    serializer_class = CouponSerializer
