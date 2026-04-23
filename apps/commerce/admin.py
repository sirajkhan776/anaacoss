from django.contrib import admin

from .models import Cart, CartItem, Coupon, Order, OrderItem, WishlistItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_name", "variant_name", "quantity", "unit_price", "line_total")


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "discount_type", "value", "minimum_order_value", "is_active", "used_count")
    list_filter = ("discount_type", "is_active")
    search_fields = ("code", "title")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_key", "coupon", "updated_at")
    inlines = [CartItemInline]


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "created_at")
    search_fields = ("user__email", "product__name")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total", "payment_method", "created_at")
    list_filter = ("status", "payment_method", "created_at")
    search_fields = ("email", "phone", "full_name")
    inlines = [OrderItemInline]
