from django.urls import path

from . import views

urlpatterns = [
    path("cart/", views.cart_page, name="cart"),
    path("checkout/", views.checkout_page, name="checkout"),
    path("add-address/", views.address_form_page, name="add-address"),
    path("addresses/<int:address_id>/edit/", views.address_form_page, name="edit-address"),
    path("wishlist/", views.wishlist_page, name="wishlist"),
    path("offers/", views.offers_page, name="offers"),
    path("dashboard/", views.dashboard_page, name="dashboard"),
    path("dashboard/profile/beauty/", views.cosmetic_profile_page, name="cosmetic-profile"),
]
