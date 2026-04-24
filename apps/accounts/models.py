from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=24, blank=True)

    REQUIRED_FIELDS = ["email"]


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to="profiles/", blank=True)
    skin_type = models.CharField(max_length=60, blank=True)
    skin_tone = models.CharField(max_length=80, blank=True)
    skin_concern = models.CharField(max_length=120, blank=True)
    hair_type = models.CharField(max_length=80, blank=True)
    hair_concern = models.CharField(max_length=120, blank=True)
    beauty_goals = models.CharField(max_length=180, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    notifications_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class ShoppingProfile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="shopping_profiles")
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    avatar = models.ImageField(upload_to="shopping_profiles/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.user.username


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=50, default="Home")
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=24)
    line1 = models.CharField(max_length=180)
    line2 = models.CharField(max_length=180, blank=True)
    city = models.CharField(max_length=80)
    state = models.CharField(max_length=80)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=80, default="India")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.label} - {self.city}"
