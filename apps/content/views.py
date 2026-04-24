from django.shortcuts import render
from rest_framework import generics, viewsets

from apps.catalog.views import base_context

from .models import Banner, NewsletterSubscriber, Testimonial
from .serializers import BannerSerializer, NewsletterSubscriberSerializer, TestimonialSerializer


def about(request):
    return render(request, "content/about.html", base_context())


def contact(request):
    return render(request, "content/contact.html", base_context())


def faq(request):
    return render(request, "content/faq.html", base_context())


def terms(request):
    return render(request, "content/terms.html", base_context())


def privacy_policy(request):
    return render(request, "content/privacy_policy.html", base_context())


def privacy_center(request):
    return render(request, "content/privacy_center.html", base_context())


class BannerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Banner.objects.filter(is_active=True)
    serializer_class = BannerSerializer


class TestimonialViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Testimonial.objects.filter(is_active=True)
    serializer_class = TestimonialSerializer


class NewsletterSubscribeView(generics.CreateAPIView):
    queryset = NewsletterSubscriber.objects.all()
    serializer_class = NewsletterSubscriberSerializer
