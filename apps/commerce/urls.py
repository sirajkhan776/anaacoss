from django.urls import path

from . import views

urlpatterns = [
    path("cart/", views.cart_page, name="cart"),
    path("checkout/", views.checkout_page, name="checkout"),
    path("wishlist/", views.wishlist_page, name="wishlist"),
    path("offers/", views.offers_page, name="offers"),
    path("dashboard/", views.dashboard_page, name="dashboard"),
]
