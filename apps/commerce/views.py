from django.shortcuts import redirect, render
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.decorators import jwt_required_page
from apps.accounts.forms import AccountDetailsForm, CosmeticProfileForm, NotificationSettingsForm
from apps.accounts.models import Profile
from apps.catalog.models import Product, ProductVariant
from apps.catalog.views import base_context

from .models import Coupon, Order, WishlistItem
from .serializers import CartSerializer, CouponSerializer, OrderSerializer, WishlistItemSerializer
from .services import get_cart, place_order


@jwt_required_page
def cart_page(request):
    ctx = base_context()
    ctx["cart"] = get_cart(request)
    ctx["selected_address"] = request.user.addresses.filter(is_default=True).first() or request.user.addresses.first()
    return render(request, "commerce/cart.html", ctx)


@jwt_required_page
def checkout_page(request):
    ctx = base_context()
    ctx["cart"] = get_cart(request)
    ctx["addresses"] = request.user.addresses.all()
    ctx["selected_address"] = request.user.addresses.filter(is_default=True).first() or request.user.addresses.first()
    return render(request, "commerce/checkout.html", ctx)


@jwt_required_page
def wishlist_page(request):
    ctx = base_context()
    ctx["wishlist_items"] = request.user.wishlist_items.select_related("product").prefetch_related("product__images")
    return render(request, "commerce/wishlist.html", ctx)


def offers_page(request):
    ctx = base_context()
    ctx["coupons"] = Coupon.objects.filter(is_active=True)
    ctx["offers"] = Product.objects.visible().filter(is_offer=True).prefetch_related("images")[:12]
    return render(request, "commerce/offers.html", ctx)


@jwt_required_page
def dashboard_page(request):
    ctx = base_context()
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "POST" and request.POST.get("form_name") == "account-details":
        account_form = AccountDetailsForm(request.POST, request.FILES, instance=request.user)
        if account_form.is_valid():
            account_form.save()
            avatar = account_form.cleaned_data.get("avatar")
            if avatar:
                profile.avatar = avatar
                profile.save(update_fields=["avatar"])
            return redirect("/dashboard/?account_saved=1&account_open=1")
    if request.method == "POST" and request.POST.get("form_name") == "notification-settings":
        settings_form = NotificationSettingsForm(request.POST, instance=profile)
        if settings_form.is_valid():
            settings_form.save()
            return redirect("/dashboard/?settings_saved=1")
    ctx["profile_user"] = request.user
    ctx["profile"] = profile
    ctx["orders"] = request.user.orders.prefetch_related("items")[:8]
    ctx["addresses"] = request.user.addresses.all()
    ctx["account_form"] = AccountDetailsForm(instance=request.user)
    ctx["account_saved"] = request.GET.get("account_saved") == "1"
    ctx["account_open"] = request.GET.get("account_open") == "1"
    ctx["settings_saved"] = request.GET.get("settings_saved") == "1"
    return render(request, "account/dashboard.html", ctx)


@jwt_required_page
def cosmetic_profile_page(request):
    ctx = base_context()
    profile, _ = Profile.objects.get_or_create(user=request.user)
    form = CosmeticProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("/dashboard/profile/beauty/?saved=1")
    ctx.update(
        {
            "cosmetic_form": form,
            "cosmetic_saved": request.GET.get("saved") == "1",
        }
    )
    return render(request, "account/cosmetic_profile.html", ctx)


@jwt_required_page
def address_form_page(request, address_id=None):
    ctx = base_context()
    address = request.user.addresses.filter(pk=address_id).first() if address_id else None
    ctx.update(
        {
            "address_record": address,
            "address_mode": "edit" if address else "create",
            "address_return_url": request.GET.get("return") or "/checkout/",
        }
    )
    return render(request, "account/address_form.html", ctx)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def cart_api(request):
    return Response(CartSerializer(get_cart(request)).data)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
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
@permission_classes([permissions.IsAuthenticated])
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
@permission_classes([permissions.IsAuthenticated])
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
        selected_item_ids = request.data.get("selected_item_ids") or []
        if isinstance(selected_item_ids, str):
            selected_item_ids = [item.strip() for item in selected_item_ids.split(",") if item.strip()]
        items_queryset = cart.items.select_related("product", "variant")
        if selected_item_ids:
            items_queryset = items_queryset.filter(id__in=selected_item_ids)
        if not items_queryset.exists():
            return Response({"selected_item_ids": ["Select at least one cart item."]}, status=status.HTTP_400_BAD_REQUEST)
        address_id = request.data.get("address_id")
        if address_id:
            address = request.user.addresses.filter(pk=address_id).first()
            if not address:
                return Response({"address_id": ["Select a valid saved address."]}, status=status.HTTP_400_BAD_REQUEST)
            payload = {
                "full_name": address.full_name,
                "email": request.user.email,
                "phone": address.phone,
                "address_line1": address.line1,
                "address_line2": address.line2,
                "city": address.city,
                "state": address.state,
                "postal_code": address.postal_code,
                "payment_method": request.data.get("payment_method", "cod"),
            }
        else:
            required = ["full_name", "email", "phone", "address_line1", "city", "state", "postal_code"]
            missing = [field for field in required if not request.data.get(field)]
            if missing:
                return Response({field: ["This field is required."] for field in missing}, status=status.HTTP_400_BAD_REQUEST)
            payload = request.data
        order = place_order(request.user, cart, payload, items_queryset=items_queryset)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class CouponViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Coupon.objects.filter(is_active=True)
    serializer_class = CouponSerializer
