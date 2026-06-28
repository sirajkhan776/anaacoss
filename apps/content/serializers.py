from rest_framework import serializers

from anaacoss.utils import absolute_media_url

from .models import Banner, NewsletterSubscriber, Testimonial


class BannerSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Banner
        fields = ("id", "title", "subtitle", "eyebrow", "image_url", "cta_label", "cta_url", "placement")

    def get_image_url(self, obj):
        return absolute_media_url(obj.image_url, self.context.get("request"))


class TestimonialSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Testimonial
        fields = ("id", "name", "role", "quote", "rating", "image_url")

    def get_image_url(self, obj):
        image_url = obj.image.url if obj.image else ""
        return absolute_media_url(image_url, self.context.get("request"))


class NewsletterSubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscriber
        fields = ("email",)
