from django.contrib import admin

from .models import Brand, Category, Product, ProductImage, ProductVariant, Review, ReviewImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    fields = ("media_type", "placement", "image", "remote_url", "video", "video_url", "thumbnail_url", "alt_text", "is_primary", "sort_order")
    extra = 1


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "is_featured", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ("is_featured", "parent")


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "is_premium")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "category", "price", "discount_price", "stock", "is_active", "is_featured")
    list_filter = ("category", "brand", "is_active", "is_featured", "is_trending", "is_offer")
    search_fields = ("name", "sku", "short_description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline, ProductVariantInline]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "is_approved", "created_at")
    list_filter = ("rating", "is_approved")
    search_fields = ("product__name", "user__email", "title")
    inlines = [ReviewImageInline]
