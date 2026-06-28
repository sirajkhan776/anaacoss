from decimal import Decimal
from pathlib import Path
import re

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Brand, Category, Product, ProductImage


IGNORED_DIRS = {"__MACOSX"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
PRODUCT_WORDS = {
    "FW": "Face Wash",
    "FACE WASH": "Face Wash",
    "FACIAL CLEANSER": "Facial Cleanser",
    "CLEANSER": "Cleanser",
    "SOAP": "Soap",
}
PRODUCT_DESCRIPTORS = tuple(sorted(PRODUCT_WORDS, key=len, reverse=True))
PRODUCT_TYPE_RULES = (
    ("PLANT HAIR CARE", "hair care soap"),
    ("HAIR CARE", "hair care soap"),
    ("BODY WHITENING SOAP", "body soap"),
    ("WHITENING SOAP", "soap"),
    ("SOAP", "soap"),
    ("FACE WASH", "facewash"),
    ("FACIAL CLEANSER", "cleanser"),
    ("CLEANSER", "cleanser"),
    ("FW", "facewash"),
)


def normalize_whitespace(value):
    return re.sub(r"\s+", " ", value or "").strip()


def clean_display_name(raw_name):
    cleaned = normalize_whitespace(raw_name.replace("_", " "))
    cleaned = cleaned.replace(" ,", ",").replace(" '", "'").replace("L,O", "L'O")
    return cleaned


def split_brand_and_product(folder_name):
    display_name = clean_display_name(folder_name)
    upper_name = display_name.upper()

    for descriptor in PRODUCT_DESCRIPTORS:
        index = upper_name.find(descriptor)
        if index == -1:
            continue
        brand_name = normalize_whitespace(display_name[:index]).strip(" -")
        suffix = PRODUCT_WORDS[descriptor]
        prefix = normalize_whitespace(display_name[index + len(descriptor):]).strip(" -")
        if prefix:
            product_name = f"{brand_name} {prefix} {suffix}".strip()
        else:
            product_name = f"{brand_name} {suffix}".strip()
        return brand_name or display_name, normalize_whitespace(product_name)

    return display_name, display_name


def infer_product_type(folder_name):
    upper_name = clean_display_name(folder_name).upper()
    for needle, product_type in PRODUCT_TYPE_RULES:
        if needle in upper_name:
            return product_type
    return "facewash"


def unique_slug(model, base_value, exclude_pk=None):
    base_slug = slugify(base_value) or "item"
    slug = base_slug
    counter = 2
    while True:
        qs = model.objects.filter(slug=slug)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1


def next_sku():
    existing_numbers = []
    for sku in Product.objects.filter(sku__startswith="PL-").values_list("sku", flat=True):
        try:
            existing_numbers.append(int(sku.split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"PL-{(max(existing_numbers) + 1) if existing_numbers else 1001}"


def get_or_create_brand(brand_name):
    brand_slug = slugify(brand_name) or "brand"
    brand = Brand.objects.filter(slug=brand_slug).first() or Brand.objects.filter(name__iexact=brand_name).first()
    if brand:
        if not brand.slug:
            brand.slug = unique_slug(Brand, brand_name, exclude_pk=brand.pk)
            brand.save(update_fields=["slug"])
        return brand

    return Brand.objects.create(
        name=brand_name,
        slug=unique_slug(Brand, brand_name),
        story=f"{brand_name} creates skincare-focused daily essentials designed for simple, effective cleansing routines.",
        is_premium=True,
    )


def build_copy(brand_name, product_name, product_type):
    lower_name = product_name.lower()
    if "charcoal" in lower_name and product_type == "facewash":
        short_description = "Deep-cleansing charcoal face wash for a fresh, clarified finish."
        description = (
            f"{product_name} by {brand_name} is a skin-refreshing daily cleanser designed to lift away "
            "oil, grime, and urban buildup without leaving skin feeling tight."
        )
        ingredients = (
            "Aqua, glycerin, activated charcoal, cocamidopropyl betaine, aloe vera extract, "
            "niacinamide, panthenol, fragrance."
        )
    elif "soothing" in lower_name and product_type in {"facewash", "cleanser"}:
        short_description = "Gentle soothing cleanser that comforts skin while washing away residue."
        description = (
            f"{product_name} by {brand_name} is a calming skincare cleanser made for daily use, "
            "helping skin feel soft, balanced, and clean after every wash."
        )
        ingredients = (
            "Aqua, glycerin, cocamidopropyl betaine, allantoin, chamomile extract, cucumber extract, "
            "panthenol, sodium hyaluronate."
        )
    elif ("luxury soft" in lower_name or "soft" in lower_name) and product_type in {"facewash", "cleanser"}:
        short_description = "Creamy face wash with a soft-lather cleanse for everyday comfort."
        description = (
            f"{product_name} by {brand_name} creates a rich, soft cleanse that removes surface impurities "
            "while keeping the skin comfortable and smooth."
        )
        ingredients = (
            "Aqua, glycerin, stearic acid, myristic acid, coconut-derived cleansers, aloe vera extract, "
            "vitamin E, fragrance."
        )
    elif product_type == "soap":
        if "kojic" in lower_name:
            short_description = "Brightening kojic soap bar for a smooth, refreshed cleanse."
            description = (
                f"{product_name} by {brand_name} is a daily cleansing bar crafted to leave skin feeling clean, "
                "polished, and refreshed with a rich, creamy wash experience."
            )
            ingredients = (
                "Sodium palmate, sodium palm kernelate, glycerin, kojic acid, niacinamide, coconut oil, "
                "fragrance, titanium dioxide."
            )
        elif "gold" in lower_name:
            short_description = "Luxury gold-infused beauty soap with a rich cleansing lather."
            description = (
                f"{product_name} by {brand_name} is a premium cleansing soap designed to wash away buildup "
                "while leaving skin soft, smooth, and freshly pampered."
            )
            ingredients = (
                "Sodium palmate, glycerin, gold mica, collagen extract, coconut-derived cleansers, "
                "vitamin E, fragrance."
            )
        elif "collagen" in lower_name:
            short_description = "Collagen beauty soap for a soft, bouncy-feel daily cleanse."
            description = (
                f"{product_name} by {brand_name} is a skincare soap bar made for daily bathing, helping skin "
                "feel supple, clean, and comforted after each use."
            )
            ingredients = (
                "Sodium palmate, glycerin, hydrolyzed collagen, aloe vera extract, shea butter, "
                "vitamin E, fragrance."
            )
        elif "vitamin c" in lower_name:
            short_description = "Vitamin C cleansing soap for a fresh, radiant-looking wash."
            description = (
                f"{product_name} by {brand_name} is a brightening soap bar that creates a generous lather "
                "and leaves skin feeling fresh, clean, and energized."
            )
            ingredients = (
                "Sodium palmate, glycerin, vitamin C derivative, citrus extract, coconut oil, "
                "niacinamide, fragrance."
            )
        elif "herbal" in lower_name:
            short_description = "Herbal soap bar with a clean rinse and balanced everyday feel."
            description = (
                f"{product_name} by {brand_name} is a herbal cleansing soap formulated for daily body care, "
                "helping wash away impurities while keeping the skin feeling comfortable."
            )
            ingredients = (
                "Sodium palmate, glycerin, neem extract, aloe vera extract, turmeric extract, "
                "tea tree oil, fragrance."
            )
        else:
            short_description = "Daily beauty soap with a rich lather and a clean, refreshed finish."
            description = (
                f"{product_name} by {brand_name} is a cleansing soap bar created for a satisfying everyday wash, "
                "leaving skin feeling clean, soft, and refreshed."
            )
            ingredients = (
                "Sodium palmate, sodium palm kernelate, glycerin, coconut oil, aloe vera extract, "
                "vitamin E, fragrance."
            )
    elif product_type == "body soap":
        short_description = "Body soap bar for a thorough cleanse and a smooth after-wash feel."
        description = (
            f"{product_name} by {brand_name} is a body-cleansing beauty bar designed to create a dense lather, "
            "rinse away daily buildup, and leave skin feeling fresh and cared for."
        )
        ingredients = (
            "Sodium palmate, glycerin, niacinamide, herbal extracts, coconut oil, shea butter, "
            "vitamin E, fragrance."
        )
    elif product_type == "hair care soap":
        short_description = "Solid hair care cleansing bar for a fresh scalp and clean strands."
        description = (
            f"{product_name} by {brand_name} is a plant-based hair care bar intended to cleanse the scalp and hair "
            "while maintaining a softer, smoother feel after washing."
        )
        ingredients = (
            "Sodium cocoyl isethionate, glycerin, ginger extract, rosemary extract, argan oil, "
            "panthenol, fragrance."
        )
    else:
        short_description = "Daily face wash that cleanses effectively and leaves skin feeling refreshed."
        description = (
            f"{product_name} by {brand_name} is a skincare essential formulated for an all-skin-type routine, "
            "offering a clean rinse, a fresh feel, and comfortable everyday use."
        )
        ingredients = (
            "Aqua, glycerin, cocamidopropyl betaine, aloe vera extract, panthenol, green tea extract, "
            "citric acid, fragrance."
        )

    if product_type in {"soap", "body soap"}:
        how_to_use = (
            "Wet the bar and work into a light lather between your hands or on damp skin, "
            "massage gently, then rinse thoroughly."
        )
    elif product_type == "hair care soap":
        how_to_use = (
            "Wet hair and scalp, glide the bar or lather in your hands first, massage into the scalp and lengths, "
            "then rinse thoroughly."
        )
    else:
        how_to_use = (
            "Apply a small amount to damp skin, massage gently over the face in circular motions, "
            "then rinse thoroughly. Use morning and evening."
        )
    return short_description, description, ingredients, how_to_use


def image_paths_for_folder(folder_path):
    return sorted(
        [
            path
            for path in folder_path.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS and not path.name.startswith("._")
        ],
        key=lambda item: item.name.lower(),
    )


class Command(BaseCommand):
    help = "Seed product listings from folder-based product image sets."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="../products_listing",
            help="Path to the folder that contains one subfolder per product listing.",
        )
        parser.add_argument(
            "--replace-images",
            action="store_true",
            help="Replace existing gallery images for products created from these folder names.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        source_dir = Path(options["source"]).resolve()
        if not source_dir.exists():
            raise CommandError(f"Source folder does not exist: {source_dir}")
        if not source_dir.is_dir():
            raise CommandError(f"Source path is not a directory: {source_dir}")

        skincare_category, _ = Category.objects.get_or_create(
            slug="skincare",
            defaults={
                "name": "Skincare",
                "description": "Serums, creams, cleansers, and rituals for luminous skin.",
                "icon": "droplet",
                "is_featured": True,
                "sort_order": 1,
            },
        )

        created_products = 0
        updated_products = 0
        uploaded_images = 0

        for folder_path in sorted(source_dir.iterdir(), key=lambda item: item.name.lower()):
            if not folder_path.is_dir() or folder_path.name in IGNORED_DIRS:
                continue

            image_paths = image_paths_for_folder(folder_path)
            if not image_paths:
                self.stdout.write(self.style.WARNING(f"Skipping {folder_path.name}: no image files found."))
                continue

            brand_name, product_name = split_brand_and_product(folder_path.name)
            product_type = infer_product_type(folder_path.name)
            brand = get_or_create_brand(brand_name)

            short_description, description, ingredients, how_to_use = build_copy(brand.name, product_name, product_type)
            sku = next_sku()
            price_seed = 249 + (sum(ord(char) for char in product_name) % 250)
            price = Decimal(str(price_seed))
            discount_price = price - Decimal("30.00") if price >= Decimal("299.00") else None
            product_slug = unique_slug(Product, product_name)
            existing_product = Product.objects.filter(slug=slugify(product_name)).first() or Product.objects.filter(name=product_name).first()

            if existing_product:
                product = existing_product
                created = False
            else:
                product = Product(
                    sku=sku,
                    slug=product_slug,
                )
                created = True

            product.name = product_name
            product.slug = product.slug if not created else product_slug
            product.brand = brand
            product.category = skincare_category
            product.short_description = short_description
            product.description = description
            product.ingredients = ingredients
            product.how_to_use = how_to_use
            product.price = price
            product.discount_price = discount_price
            product.stock = max(product.stock or 0, 24 + len(image_paths))
            product.skin_type = "all"
            product.gender = Product.GENDER_UNISEX
            product.product_type = product_type
            product.is_active = True
            product.is_featured = product.is_featured if not created else False
            product.is_trending = product.is_trending if not created else False
            product.is_best_seller = product.is_best_seller if not created else False
            product.is_new_arrival = True
            product.is_offer = discount_price is not None
            product.badge = product.badge or "New"
            if created:
                product.rating = Decimal("4.50")
                product.review_count = 0
            product.save()

            if created:
                created_products += 1
            else:
                updated_products += 1

            if created or options["replace_images"]:
                product.images.all().delete()
                for index, image_path in enumerate(image_paths):
                    with image_path.open("rb") as image_handle:
                        product_image = ProductImage(
                            product=product,
                            media_type=ProductImage.IMAGE,
                            placement=ProductImage.GALLERY,
                            alt_text=f"{product.name} image {index + 1}",
                            is_primary=index == 0,
                            sort_order=index,
                        )
                        product_image.image.save(image_path.name, File(image_handle), save=True)
                        uploaded_images += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"{'Created' if created else 'Updated'} {product.name} with {len(image_paths)} image(s) from {folder_path.name}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed product listing seed. Created: {created_products}, Updated: {updated_products}, Images uploaded: {uploaded_images}"
            )
        )
