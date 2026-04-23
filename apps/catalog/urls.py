from django.urls import path

from . import views

urlpatterns = [
    path("shop/", views.shop, name="shop"),
    path("category/<slug:category_slug>/", views.shop, name="category"),
    path("product/<slug:slug>/", views.product_detail, name="storefront-product-detail"),
]
