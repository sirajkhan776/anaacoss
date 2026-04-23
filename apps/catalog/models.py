from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg
from django.urls import reverse
from django.utils.text import slugify


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=60, default="sparkles")
    image = models.ImageField(upload_to="categories/", blank=True)
    is_featured = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Brand(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    story = models.TextField(blank=True)
    is_premium = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(is_active=True)

    def featured(self):
        return self.visible().filter(is_featured=True)

    def discounted(self):
        return self.visible().filter(discount_price__isnull=False)


class Product(TimeStampedModel):
    SKIN_TYPES = [
        ("all", "All skin types"),
        ("dry", "Dry"),
        ("oily", "Oily"),
        ("combination", "Combination"),
        ("sensitive", "Sensitive"),
        ("mature", "Mature"),
    ]

    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    short_description = models.CharField(max_length=260)
    description = models.TextField()
    ingredients = models.TextField(blank=True)
    how_to_use = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sku = models.CharField(max_length=80, unique=True)
    stock = models.PositiveIntegerField(default=0)
    skin_type = models.CharField(max_length=40, choices=SKIN_TYPES, default="all")
    product_type = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_trending = models.BooleanField(default=False)
    is_best_seller = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    is_offer = models.BooleanField(default=False)
    badge = models.CharField(max_length=60, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    review_count = models.PositiveIntegerField(default=0)
    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-is_featured", "-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active", "is_featured"]),
            models.Index(fields=["is_trending", "is_best_seller"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def final_price(self):
        return self.discount_price or self.price

    @property
    def in_stock(self):
        return self.stock > 0

    def get_absolute_url(self):
        return reverse("storefront-product-detail", kwargs={"slug": self.slug})

    def __str__(self):
        return self.name


class ProductVariant(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=90)
    value = models.CharField(max_length=90)
    price_delta = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    stock = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=90, unique=True)

    def __str__(self):
        return f"{self.product.name} - {self.name}: {self.value}"


class ProductImage(TimeStampedModel):
    IMAGE = "image"
    VIDEO = "video"
    MEDIA_TYPES = [(IMAGE, "Image"), (VIDEO, "Video")]
    GALLERY = "gallery"
    BEFORE = "before"
    AFTER = "after"
    PLACEMENTS = [(GALLERY, "Gallery"), (BEFORE, "Before"), (AFTER, "After")]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPES, default=IMAGE)
    placement = models.CharField(max_length=20, choices=PLACEMENTS, default=GALLERY)
    image = models.ImageField(upload_to="products/", blank=True)
    remote_url = models.URLField(blank=True)
    video = models.FileField(upload_to="products/videos/", blank=True)
    video_url = models.URLField(blank=True)
    thumbnail_url = models.URLField(blank=True)
    alt_text = models.CharField(max_length=140, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "-is_primary", "id"]

    @property
    def url(self):
        if self.media_type == self.VIDEO:
            if self.video:
                return self.video.url
            return self.video_url or self.remote_url
        if self.image:
            return self.image.url
        return self.remote_url

    @property
    def thumbnail(self):
        if self.thumbnail_url:
            return self.thumbnail_url
        if self.media_type == self.IMAGE:
            return self.url
        return self.remote_url

    def __str__(self):
        return self.alt_text or self.product.name


class Review(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=140)
    body = models.TextField()
    is_approved = models.BooleanField(default=True)

    class Meta:
        unique_together = ("product", "user")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product} - {self.rating}"

    def refresh_product_rating(self):
        stats = self.product.reviews.filter(is_approved=True).aggregate(avg=Avg("rating"), count=models.Count("id"))
        self.product.rating = stats["avg"] or 0
        self.product.review_count = stats["count"] or 0
        self.product.save(update_fields=["rating", "review_count"])

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.refresh_product_rating()

    def delete(self, *args, **kwargs):
        product = self.product
        result = super().delete(*args, **kwargs)
        stats = product.reviews.filter(is_approved=True).aggregate(avg=Avg("rating"), count=models.Count("id"))
        product.rating = stats["avg"] or 0
        product.review_count = stats["count"] or 0
        product.save(update_fields=["rating", "review_count"])
        return result


class ReviewImage(TimeStampedModel):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="reviews/")
    alt_text = models.CharField(max_length=140, blank=True)

    def __str__(self):
        return self.alt_text or f"Review image #{self.pk}"
