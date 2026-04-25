from collections import OrderedDict
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.decorators import jwt_required_page
from apps.accounts.forms import AccountDetailsForm, CosmeticProfileForm, NotificationSettingsForm, ShoppingProfileForm
from apps.accounts.models import Profile
from apps.catalog.models import Product, ProductVariant
from apps.catalog.views import base_context
from apps.catalog.models import Review

from .models import Coupon, Order, WishlistItem
from .serializers import CartSerializer, CouponSerializer, OrderSerializer, WishlistItemSerializer
from .services import build_invoice_pdf, ensure_invoice, get_cart, place_order


def get_user_shopping_profiles(user):
    try:
        return list(user.shopping_profiles.all())
    except (OperationalError, ProgrammingError):
        return []


def parse_selected_item_ids(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip().isdigit()]


def get_checkout_items(request, cart):
    selected_ids = parse_selected_item_ids(request.GET.get("items"))
    items = cart.items.select_related("product", "variant").prefetch_related("product__images")
    if selected_ids:
        items = items.filter(id__in=selected_ids)
        order_map = {item_id: index for index, item_id in enumerate(selected_ids)}
        return sorted(items, key=lambda item: order_map.get(str(item.id), 9999)), selected_ids
    return list(items), [str(item.id) for item in items]


def build_checkout_summary(cart, items):
    subtotal = sum((item.line_total for item in items), Decimal("0.00"))
    discount = cart.coupon.discount_for(subtotal) if cart.coupon else Decimal("0.00")
    shipping = Decimal("0.00") if subtotal >= Decimal("2500.00") or subtotal == 0 else Decimal("149.00")
    total = max(Decimal("0.00"), subtotal - discount + shipping)
    return {
        "subtotal": subtotal,
        "discount": discount,
        "shipping": shipping,
        "total": total,
        "count": sum(item.quantity for item in items),
    }


UPI_METHOD_LABELS = {
    "phonepe": "PhonePe UPI",
    "gpay": "Google Pay UPI",
    "amazon_pay_upi": "Amazon Pay UPI",
    "imobile": "iMobile (ICICI) UPI",
}


PAYMENT_METHOD_LABELS = {
    "cod": "Cash on Delivery",
    "upi": "UPI",
    "card": "Credit / Debit Card",
    "net_banking": "Net Banking",
    "wallet": "Wallet",
    **UPI_METHOD_LABELS,
}


ORDER_TRACK_STEPS = [
    ("pending", "Order placed", "We have received your order"),
    ("paid", "Confirmed", "Payment verified and order confirmed"),
    ("processing", "Packed", "Your items are being packed"),
    ("shipped", "Shipped", "Your order is on the way"),
    ("delivered", "Delivered", "Package delivered successfully"),
]


REVIEW_RATING_LABELS = {
    1: "Poor",
    2: "Okay",
    3: "Good",
    4: "Liked It!",
    5: "Loved It!",
}


ORDER_GROUP_CONFIG = OrderedDict(
    [
        ("recent", {"title": "Recent Orders", "status": "Recent Order", "icon": "fa-solid fa-box", "tone": "neutral"}),
        ("delivered", {"title": "Delivered", "status": "Delivered", "icon": "fa-solid fa-circle-check", "tone": "success"}),
        ("exchanged", {"title": "Exchanged", "status": "Exchanged", "icon": "fa-solid fa-rotate", "tone": "neutral"}),
        ("returned", {"title": "Returned", "status": "Returned", "icon": "fa-solid fa-arrow-rotate-left", "tone": "neutral"}),
        ("cancelled", {"title": "Cancelled / Returned", "status": "Cancelled", "icon": "fa-solid fa-circle-xmark", "tone": "danger"}),
    ]
)


def order_group_key(status):
    normalized = (status or "").lower()
    if normalized == Order.DELIVERED:
        return "delivered"
    if normalized == "exchanged":
        return "exchanged"
    if normalized == "returned":
        return "returned"
    if normalized == Order.CANCELLED:
        return "cancelled"
    return "recent"


def build_order_tracking(order):
    status_rank = {
        Order.PENDING: 0,
        Order.PAID: 1,
        Order.PROCESSING: 2,
        Order.SHIPPED: 3,
        Order.DELIVERED: 4,
    }
    current_rank = status_rank.get(order.status, 0)
    steps = []
    for index, (key, title, subtitle) in enumerate(ORDER_TRACK_STEPS):
        state = "upcoming"
        if order.status == Order.CANCELLED:
            state = "completed" if index == 0 else "upcoming"
        elif index < current_rank:
            state = "completed"
        elif index == current_rank:
            state = "current"
        steps.append(
            {
                "key": key,
                "title": title,
                "subtitle": subtitle,
                "state": state,
                "timestamp": order.created_at if index == 0 else None,
            }
        )
    if order.status == Order.CANCELLED:
        steps.append(
            {
                "key": "cancelled",
                "title": "Cancelled",
                "subtitle": "This order was cancelled",
                "state": "current",
                "timestamp": None,
            }
        )
    return steps


def build_order_groups(user):
    groups = OrderedDict((key, {"key": key, **config, "items": []}) for key, config in ORDER_GROUP_CONFIG.items())
    reviews = {
        review.product_id: review
        for review in Review.objects.filter(user=user).select_related("product")
    }
    orders = (
        user.orders.order_by("-created_at")
        .prefetch_related("items__product__brand", "items__product__images")
    )
    for order in orders:
        group = groups[order_group_key(order.status)]
        status_label = group["status"] if group["key"] != "recent" else order.get_status_display()
        status_prefix = "Ordered on" if group["key"] == "recent" else f"{status_label} on"
        for item in order.items.all():
            product = item.product
            primary_image = product.images.filter(is_primary=True).first() or product.images.first()
            review = reviews.get(product.id)
            group["items"].append(
                {
                    "order": order,
                    "item": item,
                    "product": product,
                    "brand_name": product.brand.name if product.brand_id else "",
                    "image_url": primary_image.url if primary_image else "",
                    "status_label": status_label,
                    "status_tone": group["tone"],
                    "status_icon": group["icon"],
                    "status_meta": f"{status_prefix} {order.created_at.strftime('%d %b %Y, %I:%M %p')}",
                    "size_label": item.variant_name or "One Size",
                    "courier_name": "",
                    "review": review,
                    "review_label": "View Review" if review else "Write Review",
                    "review_stars": int(review.rating) if review else 0,
                    "profile_name": user.first_name or user.username,
                    "product_url": product.get_absolute_url(),
                    "product_review_url": reverse("product-review", kwargs={"slug": product.slug}),
                    "order_review_url": f"{reverse('order-review', kwargs={'order_id': order.id})}?item={item.id}",
                }
            )
    return [group for group in groups.values() if group["items"]]


@jwt_required_page
def cart_page(request):
    ctx = base_context()
    ctx["cart"] = get_cart(request)
    ctx["selected_address"] = request.user.addresses.filter(is_default=True).first() or request.user.addresses.first()
    ctx["hide_header_search"] = True
    ctx["checkout_mode"] = True
    ctx["page_title"] = "Bag"
    return render(request, "commerce/cart.html", ctx)


@jwt_required_page
def checkout_page(request):
    ctx = base_context()
    cart = get_cart(request)
    selected_items, selected_item_ids = get_checkout_items(request, cart)
    addresses = request.user.addresses.all()
    selected_address_id = request.GET.get("address")
    selected_address = request.user.addresses.filter(pk=selected_address_id).first() if selected_address_id else None
    selected_address = selected_address or request.user.addresses.filter(is_default=True).first() or request.user.addresses.first()
    ctx["cart"] = cart
    ctx["addresses"] = addresses
    ctx["selected_address"] = selected_address
    ctx["checkout_items"] = selected_items
    ctx["checkout_item_ids"] = ",".join(selected_item_ids)
    ctx["checkout_summary"] = build_checkout_summary(cart, selected_items)
    ctx["delivery_estimate"] = timezone.now().date() + timedelta(days=4)
    ctx["checkout_return_url"] = f"/checkout/?items={','.join(selected_item_ids)}"
    ctx["hide_header_search"] = True
    ctx["checkout_mode"] = True
    ctx["page_title"] = "Address"
    return render(request, "commerce/checkout.html", ctx)


@jwt_required_page
def payment_view(request):
    ctx = base_context()
    cart = get_cart(request)
    selected_items, selected_item_ids = get_checkout_items(request, cart)
    selected_address_id = request.GET.get("address")
    selected_address = request.user.addresses.filter(pk=selected_address_id).first() if selected_address_id else None
    selected_address = selected_address or request.user.addresses.filter(is_default=True).first() or request.user.addresses.first()
    ctx["cart"] = cart
    ctx["selected_address"] = selected_address
    ctx["checkout_items"] = selected_items
    ctx["checkout_item_ids"] = ",".join(selected_item_ids)
    ctx["checkout_summary"] = build_checkout_summary(cart, selected_items)
    ctx["checkout_back_url"] = f"/checkout/?items={','.join(selected_item_ids)}"
    ctx["coupon_count"] = Coupon.objects.filter(is_active=True).count()
    ctx["admin_upi_id"] = settings.ADMIN_UPI_ID
    ctx["admin_upi_name"] = settings.ADMIN_NAME
    ctx["hide_header_search"] = True
    ctx["checkout_mode"] = True
    ctx["page_title"] = "Payment"
    return render(request, "commerce/payment.html", ctx)


@jwt_required_page
def payment_pending_page(request, order_id):
    ctx = base_context()
    order = request.user.orders.prefetch_related("items").filter(pk=order_id).first()
    if not order:
        return redirect("/dashboard/")
    ctx["order"] = order
    ctx["hide_header_search"] = True
    return render(request, "commerce/payment_pending.html", ctx)


payment_page = payment_view


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
    ctx["shopping_profiles"] = get_user_shopping_profiles(request.user)
    ctx["orders"] = request.user.orders.prefetch_related("items")[:8]
    ctx["addresses"] = request.user.addresses.all()
    ctx["account_form"] = AccountDetailsForm(instance=request.user)
    ctx["account_saved"] = request.GET.get("account_saved") == "1"
    ctx["account_open"] = request.GET.get("account_open") == "1"
    ctx["settings_saved"] = request.GET.get("settings_saved") == "1"
    return render(request, "account/dashboard.html", ctx)


@jwt_required_page
def my_orders_view(request):
    ctx = base_context()
    ctx["checkout_mode"] = True
    ctx["page_title"] = "My Orders"
    ctx["checkout_wallet_amount"] = 0
    ctx["order_groups"] = build_order_groups(request.user)
    return render(request, "commerce/my_orders.html", ctx)


@jwt_required_page
def my_order_detail_view(request, order_id):
    ctx = base_context()
    order = (
        request.user.orders.filter(pk=order_id)
        .prefetch_related("items__product__brand", "items__product__images")
        .first()
    )
    if not order:
        return redirect("/orders/")
    review_map = {
        review.product_id: review
        for review in Review.objects.filter(user=request.user, product__in=[item.product for item in order.items.all()])
    }
    detail_items = []
    for item in order.items.all():
        product = item.product
        primary_image = product.images.filter(is_primary=True).first() or product.images.first()
        detail_items.append(
            {
                "item": item,
                "product": product,
                "brand_name": product.brand.name if product.brand_id else "",
                "image_url": primary_image.url if primary_image else "",
                "size_label": item.variant_name or "One Size",
                "review": review_map.get(product.id),
                "product_url": product.get_absolute_url(),
                "product_review_url": reverse("product-review", kwargs={"slug": product.slug}),
                "order_review_url": f"{reverse('order-review', kwargs={'order_id': order.id})}?item={item.id}",
            }
        )
    ctx.update(
        {
            "checkout_mode": True,
            "page_title": "Order Details",
            "checkout_wallet_amount": 0,
            "order": order,
            "order_items": detail_items,
            "order_tracking_steps": build_order_tracking(order),
        }
    )
    return render(request, "commerce/order_detail.html", ctx)


@jwt_required_page
def review_order_view(request, order_id):
    ctx = base_context()
    order = (
        request.user.orders.filter(pk=order_id)
        .prefetch_related("items__product__brand", "items__product__images")
        .first()
    )
    if not order:
        return redirect("/orders/")

    item_id = request.GET.get("item")
    items = order.items.select_related("product", "product__brand")
    order_item = items.filter(pk=item_id).first() if item_id else None
    order_item = order_item or items.first()
    if not order_item:
        return redirect(f"/orders/{order.id}/")

    product = order_item.product
    primary_image = product.images.filter(is_primary=True).first() or product.images.first()
    existing_review = Review.objects.filter(user=request.user, product=product).prefetch_related("images").first()

    if request.method == "POST":
        rating_raw = str(request.POST.get("rating", "")).strip()
        review_text = str(request.POST.get("review_text", "")).strip()
        photo_files = request.FILES.getlist("photos")
        video_file = request.FILES.get("video")
        errors = []
        try:
            rating = int(rating_raw)
        except (TypeError, ValueError):
            rating = 0
        if rating not in REVIEW_RATING_LABELS:
            errors.append("Select a valid rating.")
        if not review_text:
            errors.append("Write a review before submitting.")
        if len(photo_files) > 4:
            errors.append("You can upload up to 4 photos only.")
        if video_file and video_file.size > 200 * 1024 * 1024:
            errors.append("Video size must be 200 MB or less.")

        if not errors:
            review = existing_review or Review(product=product, user=request.user)
            review.order = order
            review.order_item = order_item
            review.rating = rating
            review.title = f"{REVIEW_RATING_LABELS[rating]} - {product.name[:110]}"
            review.body = review_text
            if video_file:
                review.video = video_file
            review.save()
            if photo_files:
                review.images.all().delete()
                for image in photo_files[:4]:
                    review.images.create(image=image, alt_text=f"{product.name} review image")
            return redirect("/orders/")

        ctx["review_errors"] = errors

    ctx.update(
        {
            "checkout_mode": True,
            "page_title": "Review & Earn AnaaCossCash",
            "order": order,
            "order_item": order_item,
            "product": product,
            "product_image_url": primary_image.url if primary_image else "",
            "existing_review": existing_review,
            "review_rating_labels": REVIEW_RATING_LABELS,
            "existing_rating_label": REVIEW_RATING_LABELS.get(existing_review.rating) if existing_review else "",
        }
    )
    return render(request, "commerce/review_order.html", ctx)


@jwt_required_page
def download_invoice_pdf(request, order_id):
    order = request.user.orders.filter(pk=order_id).prefetch_related("items__product").first()
    if not order:
        return redirect("/orders/")
    invoice = ensure_invoice(order)
    if not invoice.pdf_file:
        try:
            pdf_bytes = build_invoice_pdf(invoice, request=request)
            return HttpResponse(
                pdf_bytes,
                content_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'},
            )
        except RuntimeError as exc:
            return HttpResponse(str(exc), status=500)
    return FileResponse(invoice.pdf_file.open("rb"), as_attachment=True, filename=f"{invoice.invoice_number}.pdf")


invoice_pdf_view = download_invoice_pdf


@jwt_required_page
def profile_details_page(request):
    ctx = base_context()
    if request.method == "POST":
        profile_form = ShoppingProfileForm(request.POST, request.FILES)
        if profile_form.is_valid():
            try:
                shopping_profile = profile_form.save(commit=False)
                shopping_profile.user = request.user
                shopping_profile.save()
            except (OperationalError, ProgrammingError):
                return redirect("/dashboard/")
            return redirect("/dashboard/?profile_added=1")
    ctx.update(
        {
            "shopping_profile_form": ShoppingProfileForm(),
            "profile_added": request.GET.get("saved") == "1",
        }
    )
    return render(request, "account/profile_details.html", ctx)


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
        payment_method = payload.get("payment_method", "cod")
        selected_label = payload.get("selected_payment_method") or PAYMENT_METHOD_LABELS.get(payment_method, payment_method.replace("_", " ").title())
        order = place_order(
            request.user,
            cart,
            payload,
            items_queryset=items_queryset,
            payment_status=Order.PAYMENT_PENDING,
            selected_payment_method=selected_label,
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated], url_path="start-upi")
    def start_upi(self, request):
        if not settings.ADMIN_UPI_ID:
            return Response({"upi": ["Admin UPI ID is not configured."]}, status=status.HTTP_400_BAD_REQUEST)
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
        address = request.user.addresses.filter(pk=address_id).first() if address_id else None
        if not address:
            return Response({"address_id": ["Select a valid saved address."]}, status=status.HTTP_400_BAD_REQUEST)

        app_name = request.data.get("app_name", "").strip()
        payment_method = app_name if app_name in UPI_METHOD_LABELS else "upi"
        selected_label = UPI_METHOD_LABELS.get(app_name, "UPI")
        payload = {
            "full_name": address.full_name,
            "email": request.user.email,
            "phone": address.phone,
            "address_line1": address.line1,
            "address_line2": address.line2,
            "city": address.city,
            "state": address.state,
            "postal_code": address.postal_code,
            "payment_method": payment_method,
            "selected_payment_method": selected_label,
        }
        order = place_order(
            request.user,
            cart,
            payload,
            items_queryset=items_queryset,
            payment_status=Order.PAYMENT_PENDING,
            selected_payment_method=selected_label,
        )

        amount = format(order.total, ".2f")
        params = urlencode(
            {
                "pa": settings.ADMIN_UPI_ID,
                "pn": settings.ADMIN_NAME,
                "am": amount,
                "cu": "INR",
                "tn": f"Order Payment #{order.id}",
            }
        )
        generic_url = f"upi://pay?{params}"
        intent_url = generic_url
        if app_name == "phonepe":
            intent_url = f"phonepe://pay?{params}"

        return Response(
            {
                "order_id": order.id,
                "intent_url": intent_url,
                "fallback_url": generic_url,
                "pending_url": f"/checkout/payment/pending/{order.id}/",
                "payment_status": order.payment_status,
                "selected_payment_method": order.selected_payment_method,
            },
            status=status.HTTP_201_CREATED,
        )


class CouponViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Coupon.objects.filter(is_active=True)
    serializer_class = CouponSerializer
