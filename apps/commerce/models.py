from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.catalog.models import Product, ProductVariant


class Coupon(models.Model):
    PERCENT = "percent"
    FIXED = "fixed"
    DISCOUNT_TYPES = [(PERCENT, "Percent"), (FIXED, "Fixed amount")]

    code = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES, default=PERCENT)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    active_from = models.DateTimeField(default=timezone.now)
    active_until = models.DateTimeField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(default=0, help_text="0 means unlimited")
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-active_from"]

    def is_valid_for(self, subtotal):
        now = timezone.now()
        if not self.is_active or subtotal < self.minimum_order_value:
            return False
        if self.active_until and self.active_until < now:
            return False
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False
        return self.active_from <= now

    def discount_for(self, subtotal):
        if not self.is_valid_for(subtotal):
            return Decimal("0.00")
        if self.discount_type == self.PERCENT:
            return min(subtotal, subtotal * (self.value / Decimal("100")))
        return min(subtotal, self.value)

    def __str__(self):
        return self.code


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="cart")
    session_key = models.CharField(max_length=60, blank=True, db_index=True)
    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items.select_related("product", "variant")), Decimal("0.00"))

    @property
    def discount(self):
        return self.coupon.discount_for(self.subtotal) if self.coupon else Decimal("0.00")

    @property
    def shipping(self):
        return Decimal("0.00") if self.subtotal >= Decimal("2500.00") or self.subtotal == 0 else Decimal("149.00")

    @property
    def total(self):
        return max(Decimal("0.00"), self.subtotal - self.discount + self.shipping)

    def __str__(self):
        return f"Cart #{self.pk}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.SET_NULL)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("cart", "product", "variant")

    @property
    def unit_price(self):
        return self.product.final_price + (self.variant.price_delta if self.variant else Decimal("0.00"))

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class WishlistItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="wishlisted_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} loves {self.product}"


class Order(models.Model):
    PAYMENT_PENDING = "pending"
    PAYMENT_PAID = "paid"
    PAYMENT_FAILED = "failed"
    PAYMENT_STATUSES = [
        (PAYMENT_PENDING, "Pending"),
        (PAYMENT_PAID, "Paid"),
        (PAYMENT_FAILED, "Failed"),
    ]

    PENDING = "pending"
    PAID = "paid"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    STATUSES = [
        (PENDING, "Pending"),
        (PAID, "Paid"),
        (PROCESSING, "Processing"),
        (SHIPPED, "Shipped"),
        (DELIVERED, "Delivered"),
        (CANCELLED, "Cancelled"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUSES, default=PENDING)
    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=24)
    address_line1 = models.CharField(max_length=180)
    address_line2 = models.CharField(max_length=180, blank=True)
    city = models.CharField(max_length=80)
    state = models.CharField(max_length=80)
    postal_code = models.CharField(max_length=20)
    payment_method = models.CharField(max_length=60, default="cod")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUSES, default=PAYMENT_PENDING)
    selected_payment_method = models.CharField(max_length=120, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant_name = models.CharField(max_length=120, blank=True)
    product_name = models.CharField(max_length=180)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.product_name
