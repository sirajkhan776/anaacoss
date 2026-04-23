from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.catalog.models import Brand, Category, Product, ProductImage, ProductVariant
from apps.commerce.models import Coupon
from apps.content.models import Banner, Testimonial


class Command(BaseCommand):
    help = "Seed the Anaacoss storefront with premium sample catalogue data."

    def handle(self, *args, **options):
        categories = [
            ("Makeup", "makeup", "wand-magic-sparkles", "Polished color, glow finishes, and refined complexion products."),
            ("Skincare", "skincare", "droplet", "Serums, creams, cleansers, and rituals for luminous skin."),
            ("Haircare", "haircare", "wind", "Glossing treatments and scalp-first hair care."),
            ("Fragrance", "fragrance", "spray-can-sparkles", "Layered scents with soft floral, amber, and clean notes."),
            ("Beauty Tools", "beauty-tools", "brush", "Brushes, rollers, sculpting tools, and vanity essentials."),
            ("Offers", "offers", "ticket", "Curated sets and limited-time savings."),
        ]
        category_map = {}
        for order, (name, slug, icon, description) in enumerate(categories):
            category, _ = Category.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "icon": icon, "description": description, "is_featured": True, "sort_order": order},
            )
            category_map[slug] = category

        brand, _ = Brand.objects.update_or_create(
            slug="anaacoss-atelier",
            defaults={"name": "Anaacoss Atelier", "story": "Luxury formulas for luminous everyday rituals.", "is_premium": True},
        )

        Product.objects.all().delete()
        products = [
            ("Velvet Bloom Lip Serum", "makeup", "Hydrating rose tint with lacquered shine.", "https://images.unsplash.com/photo-1586495777744-4413f21062fa?auto=format&fit=crop&w=900&q=80", 1490, 1190, "Glow Deal", True, True, False),
            ("Lumiere Peptide Cream", "skincare", "Cloud-soft peptide cream for resilient radiance.", "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=900&q=80", 3290, 2790, "Best Seller", True, True, False),
            ("Rose Quartz Blush Veil", "makeup", "Air-light blush with a soft-focus satin finish.", "https://images.unsplash.com/photo-1522338242992-e1a54906a8da?auto=format&fit=crop&w=900&q=80", 1890, None, "New", True, False, True),
            ("Silk Repair Hair Elixir", "haircare", "Gloss oil with featherlight shine and heat care.", "https://images.unsplash.com/photo-1527799820374-dcf8d9d4a388?auto=format&fit=crop&w=900&q=80", 2490, 2190, "Offer", False, False, True),
            ("Noir Petal Eau de Parfum", "fragrance", "Black rose, vanilla silk, and warm amber.", "https://images.unsplash.com/photo-1541643600914-78b084683601?auto=format&fit=crop&w=900&q=80", 4990, None, "Signature", True, True, False),
            ("Sculpt Ritual Gua Sha", "beauty-tools", "Cooling rose stone facial sculpting tool.", "https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?auto=format&fit=crop&w=900&q=80", 1290, 990, "Limited", False, False, True),
            ("Pearl Dew Essence", "skincare", "Milky essence with niacinamide and pearl luminosity.", "https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=900&q=80", 2190, None, "Trending", True, False, True),
            ("Satin Skin Foundation", "makeup", "Breathable complexion tint with soft satin coverage.", "https://images.unsplash.com/photo-1599733589046-10c005739ef1?auto=format&fit=crop&w=900&q=80", 2590, 2290, "Shade Edit", True, True, False),
        ]
        for idx, (name, category_slug, short, image, price, discount, badge, trending, best, new) in enumerate(products, start=1):
            product = Product.objects.create(
                name=name,
                brand=brand,
                category=category_map[category_slug],
                short_description=short,
                description=f"{name} is crafted for a refined beauty ritual with elegant payoff and comfortable wear.",
                ingredients="Aqua, glycerin, botanical extracts, skin-conditioning emollients, fragrance where applicable.",
                how_to_use="Apply as part of your morning or evening ritual. Layer gently and build as desired.",
                price=Decimal(str(price)),
                discount_price=Decimal(str(discount)) if discount else None,
                sku=f"ANNA-{idx:03d}",
                stock=40 + idx,
                skin_type="all",
                product_type=category_slug,
                is_active=True,
                is_featured=idx <= 6,
                is_trending=trending,
                is_best_seller=best,
                is_new_arrival=new,
                is_offer=discount is not None,
                badge=badge,
                rating=Decimal("4.8"),
                review_count=18 + idx,
            )
            ProductImage.objects.create(
                product=product,
                media_type=ProductImage.IMAGE,
                placement=ProductImage.GALLERY,
                remote_url=image,
                alt_text=name,
                is_primary=True,
            )
            ProductImage.objects.create(
                product=product,
                media_type=ProductImage.IMAGE,
                placement=ProductImage.GALLERY,
                remote_url=image.replace("w=900", "w=901"),
                alt_text=f"{name} alternate",
                sort_order=2,
            )
            ProductImage.objects.create(
                product=product,
                media_type=ProductImage.VIDEO,
                placement=ProductImage.GALLERY,
                video_url="https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
                thumbnail_url=image,
                alt_text=f"{name} texture video",
                sort_order=3,
            )
            ProductImage.objects.create(
                product=product,
                media_type=ProductImage.IMAGE,
                placement=ProductImage.BEFORE,
                remote_url="https://images.unsplash.com/photo-1515377905703-c4788e51af15?auto=format&fit=crop&w=900&q=80",
                alt_text=f"{name} before result",
                sort_order=10,
            )
            ProductImage.objects.create(
                product=product,
                media_type=ProductImage.VIDEO,
                placement=ProductImage.AFTER,
                video_url="https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
                thumbnail_url=image,
                alt_text=f"{name} after result video",
                sort_order=11,
            )
            if category_slug in {"makeup", "skincare", "fragrance"}:
                ProductVariant.objects.create(product=product, name="Size", value="Full size", sku=f"ANNA-{idx:03d}-FULL", stock=30)
                ProductVariant.objects.create(product=product, name="Size", value="Travel", sku=f"ANNA-{idx:03d}-TRAVEL", stock=15, price_delta=Decimal("-300"))

        Coupon.objects.update_or_create(
            code="ROSEGOLD20",
            defaults={
                "title": "20% off Rose Gold Week",
                "description": "A luxury beauty saving on qualifying carts.",
                "discount_type": Coupon.PERCENT,
                "value": Decimal("20"),
                "minimum_order_value": Decimal("2500"),
                "active_from": timezone.now(),
                "is_active": True,
            },
        )
        Coupon.objects.update_or_create(
            code="LUXE500",
            defaults={
                "title": "Rs. 500 off premium rituals",
                "description": "Use on curated beauty edits.",
                "discount_type": Coupon.FIXED,
                "value": Decimal("500"),
                "minimum_order_value": Decimal("4000"),
                "active_from": timezone.now(),
                "is_active": True,
            },
        )

        Banner.objects.update_or_create(
            title="Luminous ritual collection",
            placement="hero",
            defaults={
                "eyebrow": "New season",
                "subtitle": "Premium cosmetics for modern radiance.",
                "remote_url": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?auto=format&fit=crop&w=1800&q=85",
                "cta_label": "Shop now",
                "cta_url": "/shop/",
                "is_active": True,
            },
        )
        for name, role, quote in [
            ("Aanya Mehra", "Beauty editor", "The textures feel expensive, but the checkout is wonderfully effortless."),
            ("Nisha Rao", "Makeup artist", "The shade edit and finish selection feel like a real boutique curation."),
            ("Sara Kapoor", "Skincare client", "My routine looks beautiful on the shelf and performs even better."),
        ]:
            Testimonial.objects.update_or_create(name=name, defaults={"role": role, "quote": quote, "rating": 5, "is_active": True})

        self.stdout.write(self.style.SUCCESS("Anaacoss sample store seeded."))
