from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update a superuser from environment variables."

    def handle(self, *args, **options):
        User = get_user_model()
        username = (self.get_env("DJANGO_SUPERUSER_USERNAME") or "").strip()
        email = (self.get_env("DJANGO_SUPERUSER_EMAIL") or "").strip()
        password = self.get_env("DJANGO_SUPERUSER_PASSWORD") or ""

        if not username or not email or not password:
            self.stdout.write(
                self.style.WARNING(
                    "Skipping admin user creation. Set DJANGO_SUPERUSER_USERNAME, "
                    "DJANGO_SUPERUSER_EMAIL, and DJANGO_SUPERUSER_PASSWORD."
                )
            )
            return

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        changed = False
        if user.email != email:
            user.email = email
            changed = True
        if not user.is_staff:
            user.is_staff = True
            changed = True
        if not user.is_superuser:
            user.is_superuser = True
            changed = True
        user.set_password(password)
        changed = True
        if changed:
            user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created admin user '{username}'"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated admin user '{username}'"))

    @staticmethod
    def get_env(name):
        from os import environ

        return environ.get(name)
