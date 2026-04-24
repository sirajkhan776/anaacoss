from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.catalog.models import Product


class Command(BaseCommand):
    help = "Load storefront seed data for local or deployment environments."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-run the product seed even if products already exist.",
        )

    def handle(self, *args, **options):
        product_count = Product.objects.count()
        if product_count and not options["force"]:
            self.stdout.write(self.style.WARNING(f"Skipping seed load. {product_count} products already exist. Use --force to reseed."))
            return

        call_command("seed_store")
        self.stdout.write(self.style.SUCCESS("Storefront seed data loaded successfully."))
