from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction

from .models import Cart, Coupon, Order, OrderItem


def get_cart(request):
    if not request.user.is_authenticated:
        raise PermissionDenied("Authentication credentials were not provided.")
    cart, _ = Cart.objects.get_or_create(user=request.user)
    return cart


def merge_session_cart(request, user):
    return None


def build_order_amounts(cart, items):
    subtotal = sum((item.line_total for item in items), Decimal("0.00"))
    discount = Decimal("0.00")
    if cart.coupon and cart.subtotal:
        discount = min(subtotal, cart.discount * (subtotal / cart.subtotal))
    shipping = Decimal("0.00") if subtotal >= Decimal("2500.00") or subtotal == 0 else Decimal("149.00")
    total = max(Decimal("0.00"), subtotal - discount + shipping)
    return subtotal, discount, shipping, total


@transaction.atomic
def place_order(user, cart, data, items_queryset=None, *, payment_status=Order.PAYMENT_PENDING, selected_payment_method=""):
    items_queryset = items_queryset or cart.items.select_related("product", "variant")
    items = list(items_queryset)
    subtotal, discount, shipping, total = build_order_amounts(cart, items)
    order = Order.objects.create(
        user=user,
        coupon=cart.coupon,
        full_name=data["full_name"],
        email=data["email"],
        phone=data["phone"],
        address_line1=data["address_line1"],
        address_line2=data.get("address_line2", ""),
        city=data["city"],
        state=data["state"],
        postal_code=data["postal_code"],
        payment_method=data.get("payment_method", "cod"),
        payment_status=payment_status,
        selected_payment_method=selected_payment_method or data.get("selected_payment_method", ""),
        subtotal=subtotal,
        discount=discount,
        shipping=shipping,
        total=total,
    )
    for item in items:
        OrderItem.objects.create(
            order=order,
            product=item.product,
            product_name=item.product.name,
            variant_name=f"{item.variant.name}: {item.variant.value}" if item.variant else "",
            quantity=item.quantity,
            unit_price=item.unit_price,
            line_total=item.line_total,
        )
        item.product.stock = max(0, item.product.stock - item.quantity)
        item.product.save(update_fields=["stock"])
    if cart.coupon:
        Coupon.objects.filter(id=cart.coupon_id).update(used_count=cart.coupon.used_count + 1)
    cart.items.filter(id__in=[item.id for item in items]).delete()
    cart.coupon = None
    cart.save(update_fields=["coupon"])
    return order
