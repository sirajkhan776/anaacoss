from django.urls import path

from . import views

urlpatterns = [
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("faq/", views.faq, name="faq"),
    path("terms/", views.terms, name="terms"),
    path("privacy/", views.privacy_policy, name="privacy-policy"),
    path("privacy-center/", views.privacy_center, name="privacy-center"),
]
