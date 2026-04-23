from rest_framework import serializers

from .models import Banner, NewsletterSubscriber, Testimonial


class BannerSerializer(serializers.ModelSerializer):
    image_url = serializers.ReadOnlyField()

    class Meta:
        model = Banner
        fields = ("id", "title", "subtitle", "eyebrow", "image_url", "cta_label", "cta_url", "placement")


class TestimonialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Testimonial
        fields = ("id", "name", "role", "quote", "rating")


class NewsletterSubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscriber
        fields = ("email",)
