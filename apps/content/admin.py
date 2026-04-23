from django.contrib import admin

from .models import Banner, NewsletterSubscriber, Testimonial


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ("title", "placement", "is_active", "sort_order")
    list_filter = ("placement", "is_active")
    search_fields = ("title", "subtitle")


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "rating", "is_active")
    list_filter = ("rating", "is_active")


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "created_at")
    search_fields = ("email",)
