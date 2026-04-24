from rest_framework import serializers

from apps.catalog.serializers import ProductCardSerializer

from .models import Cart, CartItem, Coupon, Order, OrderItem, WishlistItem


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ("id", "code", "title", "description", "discount_type", "value", "minimum_order_value")


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductCardSerializer(read_only=True)
    unit_price = serializers.ReadOnlyField()
    line_total = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = ("id", "product", "variant", "quantity", "unit_price", "line_total")


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    coupon = CouponSerializer(read_only=True)
    subtotal = serializers.ReadOnlyField()
    discount = serializers.ReadOnlyField()
    shipping = serializers.ReadOnlyField()
    total = serializers.ReadOnlyField()
    count = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ("id", "items", "coupon", "subtotal", "discount", "shipping", "total", "count")

    def get_count(self, obj):
        return sum(item.quantity for item in obj.items.all())


class WishlistItemSerializer(serializers.ModelSerializer):
    product = ProductCardSerializer(read_only=True)

    class Meta:
        model = WishlistItem
        fields = ("id", "product", "created_at")


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("product_name", "variant_name", "quantity", "unit_price", "line_total")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "payment_status",
            "selected_payment_method",
            "full_name",
            "email",
            "phone",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "payment_method",
            "subtotal",
            "discount",
            "shipping",
            "total",
            "created_at",
            "items",
        )
        read_only_fields = ("status", "payment_status", "selected_payment_method", "subtotal", "discount", "shipping", "total", "created_at")
