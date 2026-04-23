from django.db import transaction

from .models import Cart, CartItem, Coupon, Order, OrderItem


def get_cart(request):
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart
    if not request.session.session_key:
        request.session.create()
    cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key, user=None)
    return cart


def merge_session_cart(request, user):
    session_key = request.session.session_key
    if not session_key:
        return
    anon_cart = Cart.objects.filter(session_key=session_key, user=None).first()
    if not anon_cart:
        return
    user_cart, _ = Cart.objects.get_or_create(user=user)
    for item in anon_cart.items.all():
        existing, created = CartItem.objects.get_or_create(
            cart=user_cart,
            product=item.product,
            variant=item.variant,
            defaults={"quantity": item.quantity},
        )
        if not created:
            existing.quantity += item.quantity
            existing.save(update_fields=["quantity"])
    if anon_cart.coupon and not user_cart.coupon:
        user_cart.coupon = anon_cart.coupon
        user_cart.save(update_fields=["coupon"])
    anon_cart.delete()


@transaction.atomic
def place_order(user, cart, data):
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
        subtotal=cart.subtotal,
        discount=cart.discount,
        shipping=cart.shipping,
        total=cart.total,
    )
    for item in cart.items.select_related("product", "variant"):
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
    cart.items.all().delete()
    cart.coupon = None
    cart.save(update_fields=["coupon"])
    return order
