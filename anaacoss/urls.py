from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from anaacoss.sitemaps import CategorySitemap, ProductSitemap, StaticViewSitemap
from anaacoss.views import robots_txt
from apps.catalog.views import BrandViewSet, CategoryViewSet, ProductViewSet, ReviewViewSet, home
from apps.commerce.views import CouponViewSet, OrderViewSet, WishlistViewSet, add_to_cart, cart_api, cart_item_api, coupon_api
from apps.content.views import BannerViewSet, NewsletterSubscribeView, TestimonialViewSet

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("brands", BrandViewSet, basename="brand")
router.register("products", ProductViewSet, basename="product")
router.register("reviews", ReviewViewSet, basename="review")
router.register("wishlist", WishlistViewSet, basename="wishlist")
router.register("orders", OrderViewSet, basename="order")
router.register("coupons", CouponViewSet, basename="coupon")
router.register("banners", BannerViewSet, basename="banner")
router.register("testimonials", TestimonialViewSet, basename="testimonial")

sitemaps = {
    "static": StaticViewSitemap,
    "categories": CategorySitemap,
    "products": ProductSitemap,
}

urlpatterns = [
    path("", home, name="home"),
    path("robots.txt", robots_txt, name="robots-txt"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path("", include("apps.catalog.urls")),
    path("", include("apps.commerce.urls")),
    path("", include("apps.content.urls")),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include(router.urls)),
    path("api/cart/", cart_api, name="api-cart"),
    path("api/cart/add/", add_to_cart, name="api-cart-add"),
    path("api/cart/items/<int:item_id>/", cart_item_api, name="api-cart-item"),
    path("api/cart/coupon/", coupon_api, name="api-cart-coupon"),
    path("api/newsletter/", NewsletterSubscribeView.as_view(), name="api-newsletter"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
