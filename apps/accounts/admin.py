from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from django.shortcuts import redirect, render
from django.urls import path, reverse

from .forms import SuperAdminPasswordChangeForm, SuperAdminRegistrationForm
from .models import Address, Profile, ShoppingProfile, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "date_joined")
    search_fields = ("username", "email", "first_name", "last_name")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "skin_type", "hair_type", "notifications_enabled", "created_at")
    search_fields = ("user__username", "user__email", "skin_type", "skin_tone", "hair_type")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "city", "state", "postal_code", "is_default")
    list_filter = ("state", "is_default")
    search_fields = ("user__email", "full_name", "phone", "city")


@admin.register(ShoppingProfile)
class ShoppingProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "first_name", "last_name", "created_at")
    search_fields = ("user__email", "user__username", "first_name", "last_name")


admin.site.index_template = "admin/custom_index.html"


def register_superadmin_view(request):
    if request.method == "POST":
        form = SuperAdminRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Admin user '{user.username}' created successfully.")
            return redirect("admin:accounts_register_superadmin")
    else:
        form = SuperAdminRegistrationForm()

    context = {
        **admin.site.each_context(request),
        "title": "Register admin user",
        "form": form,
        "opts": User._meta,
        "change_password_url": reverse("admin:accounts_change_superadmin_password"),
    }
    return render(request, "admin/accounts/register_superadmin.html", context)


def change_superadmin_password_view(request):
    if request.method == "POST":
        form = SuperAdminPasswordChangeForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Password updated for admin user '{user.username}'.")
            return redirect("admin:accounts_change_superadmin_password")
    else:
        form = SuperAdminPasswordChangeForm()

    context = {
        **admin.site.each_context(request),
        "title": "Change admin password",
        "form": form,
        "opts": User._meta,
        "register_url": reverse("admin:accounts_register_superadmin"),
    }
    return render(request, "admin/accounts/change_superadmin_password.html", context)


original_get_urls = admin.site.get_urls


def custom_admin_urls():
    custom_urls = [
        path(
            "superadmin/register/",
            admin.site.admin_view(register_superadmin_view),
            name="accounts_register_superadmin",
        ),
        path(
            "superadmin/change-password/",
            admin.site.admin_view(change_superadmin_password_view),
            name="accounts_change_superadmin_password",
        ),
    ]
    return custom_urls + original_get_urls()


admin.site.get_urls = custom_admin_urls
