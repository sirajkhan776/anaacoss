from django.db import models


class Banner(models.Model):
    PLACEMENTS = [
        ("hero", "Hero"),
        ("offer", "Offer"),
        ("shop", "Shop"),
    ]

    title = models.CharField(max_length=160)
    subtitle = models.CharField(max_length=220, blank=True)
    eyebrow = models.CharField(max_length=80, blank=True)
    image = models.ImageField(upload_to="banners/", blank=True)
    remote_url = models.URLField(blank=True)
    cta_label = models.CharField(max_length=60, blank=True)
    cta_url = models.CharField(max_length=200, blank=True)
    placement = models.CharField(max_length=20, choices=PLACEMENTS, default="hero")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    @property
    def image_url(self):
        if self.image:
            return self.image.url
        return self.remote_url

    def __str__(self):
        return self.title


class Testimonial(models.Model):
    name = models.CharField(max_length=120)
    role = models.CharField(max_length=120, blank=True)
    quote = models.TextField()
    rating = models.PositiveSmallIntegerField(default=5)
    image = models.ImageField(upload_to="testimonials/", blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email
