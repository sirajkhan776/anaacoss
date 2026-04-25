from django.urls import path

from . import views

urlpatterns = [
    path("orders/", views.my_orders_view, name="my-orders"),
    path("orders/<int:order_id>/", views.my_order_detail_view, name="my-order-detail"),
    path("orders/<int:order_id>/review/", views.review_order_view, name="order-review"),
    path("cart/", views.cart_page, name="cart"),
    path("checkout/", views.checkout_page, name="checkout"),
    path("checkout/payment/", views.payment_view, name="payment"),
    path("checkout/payment/pending/<int:order_id>/", views.payment_pending_page, name="payment-pending"),
    path("add-address/", views.address_form_page, name="add-address"),
    path("addresses/<int:address_id>/edit/", views.address_form_page, name="edit-address"),
    path("wishlist/", views.wishlist_page, name="wishlist"),
    path("offers/", views.offers_page, name="offers"),
    path("dashboard/", views.dashboard_page, name="dashboard"),
    path("dashboard/profile/details/", views.profile_details_page, name="profile-details"),
    path("dashboard/profile/beauty/", views.cosmetic_profile_page, name="cosmetic-profile"),
]
