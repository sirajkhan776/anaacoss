from django.core.management.base import BaseCommand

from apps.catalog.management.commands.seed_product_listing import (
    BRAND_MODIFIER_WORDS,
    clean_display_name,
)
from apps.catalog.models import Brand


def canonical_brand_name(name):
    display_name = clean_display_name(name)
    tokens = display_name.split()
    if len(tokens) <= 1:
        return display_name

    parts = [tokens[0]]
    for token in tokens[1:]:
        if token.upper() in BRAND_MODIFIER_WORDS:
            break
        parts.append(token)
    return " ".join(parts).strip() or display_name


class Command(BaseCommand):
    help = "Merge duplicate seed-created brands such as 'SADOER GOLD FOIL' into their canonical brand."

    def handle(self, *args, **options):
        merged_count = 0
        moved_products = 0
        renamed_count = 0

        brands = list(Brand.objects.order_by("name"))
        canonical_map = {}

        for brand in brands:
            canonical_name = canonical_brand_name(brand.name)
            canonical = canonical_map.get(canonical_name)
            if canonical is None:
                if brand.name != canonical_name:
                    canonical = Brand.objects.filter(name__iexact=canonical_name).exclude(pk=brand.pk).first()
                    if canonical is None:
                        old_name = brand.name
                        brand.name = canonical_name
                        from django.utils.text import slugify

                        brand.slug = slugify(canonical_name) or brand.slug
                        brand.save(update_fields=["name", "slug"])
                        renamed_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Renamed brand '{old_name}' to canonical brand '{brand.name}'."
                            )
                        )
                        canonical = brand
                    canonical_map[canonical_name] = canonical
                else:
                    canonical_map[canonical_name] = brand
                continue

            if canonical.pk == brand.pk:
                continue

            product_qs = brand.products.all()
            product_total = product_qs.count()
            if product_total:
                product_qs.update(brand=canonical)
                moved_products += product_total

            brand.delete()
            merged_count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"Merged brand '{brand.name}' into '{canonical.name}' and moved {product_total} product(s)."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Brand merge complete. Brands renamed: {renamed_count}, duplicate brands removed: {merged_count}, products reassigned: {moved_products}."
            )
        )
