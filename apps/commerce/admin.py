from django.contrib import admin

from .models import Cart, CartItem, Coupon, Invoice, InvoiceItem, Order, OrderItem, WishlistItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_name", "variant_name", "quantity", "unit_price", "line_total")


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    readonly_fields = (
        "product_name",
        "sku",
        "hsn_code",
        "gst_rate",
        "quantity",
        "gross_amount",
        "discount_amount",
        "taxable_amount",
        "cgst_amount",
        "sgst_amount",
        "igst_amount",
        "total_amount",
    )


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
    list_display = ("id", "user", "status", "payment_status", "total", "payment_method", "created_at")
    list_filter = ("status", "payment_status", "payment_method", "created_at")
    search_fields = ("id", "email", "phone", "full_name", "razorpay_order_id", "razorpay_payment_id")
    readonly_fields = (
        "selected_payment_method",
        "razorpay_order_id",
        "razorpay_payment_id",
        "razorpay_signature",
        "subtotal",
        "discount",
        "shipping",
        "total",
        "created_at",
    )
    inlines = [OrderItemInline]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "order", "customer_name", "total_amount", "invoice_date", "created_at")
    list_filter = ("invoice_date", "created_at")
    search_fields = ("invoice_number", "customer_name", "order__id")
    readonly_fields = (
        "order",
        "invoice_number",
        "packet_id",
        "invoice_date",
        "order_date",
        "transaction_type",
        "supply_type",
        "place_of_supply",
        "customer_name",
        "billing_address",
        "shipping_address",
        "customer_type",
        "seller_name",
        "seller_address",
        "seller_gstin",
        "gross_amount",
        "discount_amount",
        "other_charges",
        "taxable_amount",
        "cgst_amount",
        "sgst_amount",
        "igst_amount",
        "cess_amount",
        "total_amount",
        "pdf_file",
        "created_at",
    )
    inlines = [InvoiceItemInline]
