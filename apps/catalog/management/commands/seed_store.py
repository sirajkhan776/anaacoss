from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.catalog.models import Brand, Category, Product, ProductImage, ProductVariant
from apps.commerce.models import Coupon
from apps.content.models import Banner, Testimonial


class Command(BaseCommand):
    help = "Seed the Anaacoss storefront with a large shopping-app style catalogue."

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

        brands = {
            "anaacoss-atelier": {
                "name": "Anaacoss Atelier",
                "story": "Luxury formulas for luminous everyday rituals.",
            },
            "veloura-labs": {
                "name": "Veloura Labs",
                "story": "High-performance beauty built for modern routines.",
            },
            "amber-veil": {
                "name": "Amber Veil",
                "story": "Warm fragrance and sensorial self-care edits.",
            },
            "lune-form": {
                "name": "Lune Form",
                "story": "Sculpted makeup, body, and hair essentials.",
            },
            "dewsmith": {
                "name": "Dewsmith",
                "story": "Clean hydration-forward skincare and prep staples.",
            },
        }
        brand_map = {
            slug: Brand.objects.update_or_create(
                slug=slug,
                defaults={"name": data["name"], "story": data["story"], "is_premium": True},
            )[0]
            for slug, data in brands.items()
        }

        Product.objects.all().delete()

        image_bank = {
            "makeup": [
                "https://images.unsplash.com/photo-1586495777744-4413f21062fa?auto=format&fit=crop&w=900&q=80",
                "https://images.unsplash.com/photo-1522338242992-e1a54906a8da?auto=format&fit=crop&w=900&q=80",
                "https://images.unsplash.com/photo-1599733589046-10c005739ef1?auto=format&fit=crop&w=900&q=80",
            ],
            "skincare": [
                "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=900&q=80",
                "https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=900&q=80",
                "https://images.unsplash.com/photo-1570194065650-d99fb4bedf0f?auto=format&fit=crop&w=900&q=80",
            ],
            "haircare": [
                "https://images.unsplash.com/photo-1527799820374-dcf8d9d4a388?auto=format&fit=crop&w=900&q=80",
                "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=900&q=80",
                "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=900&q=80",
            ],
            "fragrance": [
                "https://images.unsplash.com/photo-1541643600914-78b084683601?auto=format&fit=crop&w=900&q=80",
                "https://images.unsplash.com/photo-1594035910387-fea47794261f?auto=format&fit=crop&w=900&q=80",
                "https://images.unsplash.com/photo-1615634260167-c8cdede054de?auto=format&fit=crop&w=900&q=80",
            ],
            "beauty-tools": [
                "https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?auto=format&fit=crop&w=900&q=80",
                "https://images.unsplash.com/photo-1512496015851-a90fb38ba796?auto=format&fit=crop&w=900&q=80",
                "https://images.unsplash.com/photo-1616394584738-fc6e612e71b9?auto=format&fit=crop&w=900&q=80",
            ],
        }

        category_specs = {
            "makeup": {
                "brand_slugs": ["anaacoss-atelier", "veloura-labs", "lune-form"],
                "genders": [Product.GENDER_FEMALE, Product.GENDER_UNISEX, Product.GENDER_FEMALE],
                "name_templates": [
                    "Velvet Bloom Lip Color",
                    "Soft Focus Skin Tint",
                    "Cloud Kiss Blush",
                    "Satin Stroke Kajal",
                    "Glow Edit Highlighter",
                    "Mirror Shine Gloss",
                    "Lash Lift Mascara",
                    "Air Matte Lip Cream",
                    "Rose Melt Primer",
                    "Studio Wear Concealer",
                ],
                "descriptions": [
                    "Buildable payoff with smooth wear and a polished everyday finish.",
                    "Designed for fast makeup routines with comfort-first textures.",
                    "A flattering color story that feels light, refined, and wearable.",
                ],
                "price_start": 699,
            },
            "skincare": {
                "brand_slugs": ["anaacoss-atelier", "dewsmith", "veloura-labs"],
                "genders": [Product.GENDER_UNISEX, Product.GENDER_FEMALE, Product.GENDER_UNISEX],
                "name_templates": [
                    "Barrier Reset Cleanser",
                    "Hydra Dew Moisturizer",
                    "Peptide Repair Cream",
                    "Glass Skin Serum",
                    "Overnight Bounce Mask",
                    "Vitamin Glow Essence",
                    "Calm Cloud Sunscreen",
                    "Niacinamide Water Gel",
                    "Bright Start Toner",
                    "Silk Recovery Eye Cream",
                ],
                "descriptions": [
                    "Hydration-led skincare with a smooth, fresh-skin afterfeel.",
                    "Built to support barrier comfort, clarity, and daily glow.",
                    "Layer-friendly formulas for a simple but elevated routine.",
                ],
                "price_start": 849,
            },
            "haircare": {
                "brand_slugs": ["lune-form", "dewsmith", "anaacoss-atelier"],
                "genders": [Product.GENDER_FEMALE, Product.GENDER_UNISEX, Product.GENDER_MALE],
                "name_templates": [
                    "Silk Repair Hair Oil",
                    "Root Lift Scalp Serum",
                    "Gloss Guard Shampoo",
                    "Soft Wave Curl Cream",
                    "Mirror Smooth Hair Mask",
                    "Volume Reset Dry Shampoo",
                    "Moisture Wrap Conditioner",
                    "Heat Shield Styling Mist",
                    "Overnight Scalp Tonic",
                    "Frizz Calm Finishing Balm",
                ],
                "descriptions": [
                    "Scalp-first care with glossy lengths and a lighter finish.",
                    "Made for quick grooming, styling control, and smoother strands.",
                    "Everyday hair support without heavy residue or stiffness.",
                ],
                "price_start": 749,
            },
            "fragrance": {
                "brand_slugs": ["amber-veil", "anaacoss-atelier", "veloura-labs"],
                "genders": [Product.GENDER_UNISEX, Product.GENDER_FEMALE, Product.GENDER_MALE],
                "name_templates": [
                    "Noir Petal Eau de Parfum",
                    "Amber Haze Mist",
                    "Velvet Cedar Spray",
                    "Rose Smoke Perfume",
                    "Golden Hour Body Mist",
                    "Soft Leather Cologne",
                    "Moon Bloom Scent Veil",
                    "Citrus Silk Eau Fraiche",
                    "Spice Cashmere Elixir",
                    "Midnight Bloom Roll On",
                ],
                "descriptions": [
                    "Layered notes with soft diffusion and polished day-to-night wear.",
                    "A signature scent profile with a balanced modern trail.",
                    "Blended for gifting, travel, and standout everyday use.",
                ],
                "price_start": 999,
            },
            "beauty-tools": {
                "brand_slugs": ["lune-form", "anaacoss-atelier", "dewsmith"],
                "genders": [Product.GENDER_UNISEX, Product.GENDER_FEMALE, Product.GENDER_UNISEX],
                "name_templates": [
                    "Sculpt Ritual Gua Sha",
                    "Precision Blend Brush",
                    "Mirror Glow Puff Set",
                    "Contour Grip Sponge",
                    "Cooling Eye Roller",
                    "Ceramic Blowout Brush",
                    "Travel Vanity Kit",
                    "Scalp Massage Comb",
                    "Air Finish Powder Brush",
                    "Rose Detail Tweezer",
                ],
                "descriptions": [
                    "Functional beauty tools designed for clean application and travel ease.",
                    "Simple, effective accessories that upgrade daily routines.",
                    "Made to pair with modern makeup, skincare, and hair rituals.",
                ],
                "price_start": 399,
            },
        }

        badge_cycle = ["Best Seller", "Trending", "New", "Limited", "Glow Deal", "Offer", "Signature", "Popular"]
        product_counter = 1

        for category_slug, spec in category_specs.items():
            for idx in range(30):
                name = spec["name_templates"][idx % len(spec["name_templates"])]
                brand = brand_map[spec["brand_slugs"][idx % len(spec["brand_slugs"])]]
                gender = spec["genders"][idx % len(spec["genders"])]
                base_price = spec["price_start"] + (idx * 87)
                price = Decimal(str(base_price))
                discount = price - Decimal("120") if idx % 3 == 0 else None
                image = image_bank[category_slug][idx % len(image_bank[category_slug])]
                product = Product.objects.create(
                    name=f"{name} {idx + 1}",
                    brand=brand,
                    category=category_map[category_slug],
                    short_description=spec["descriptions"][idx % len(spec["descriptions"])],
                    description=f"{name} {idx + 1} is designed for a premium shopping-app style catalogue with realistic beauty details and strong everyday appeal.",
                    ingredients="Aqua, glycerin, botanical extracts, conditioning agents, fragrance where applicable.",
                    how_to_use="Apply as part of your daily ritual and layer as needed for finish, comfort, and performance.",
                    price=price,
                    discount_price=discount,
                    sku=f"ANNA-{product_counter:04d}",
                    stock=0 if idx % 17 == 0 else 24 + idx,
                    skin_type="all",
                    gender=gender,
                    product_type=category_slug,
                    is_active=True,
                    is_featured=product_counter <= 18,
                    is_trending=idx % 5 == 0,
                    is_best_seller=idx % 6 == 0,
                    is_new_arrival=idx % 4 == 0,
                    is_offer=discount is not None,
                    badge=badge_cycle[idx % len(badge_cycle)],
                    rating=Decimal(f"4.{(idx % 7) + 2}"),
                    review_count=22 + idx,
                )
                ProductImage.objects.create(
                    product=product,
                    media_type=ProductImage.IMAGE,
                    placement=ProductImage.GALLERY,
                    remote_url=image,
                    alt_text=product.name,
                    is_primary=True,
                )
                ProductImage.objects.create(
                    product=product,
                    media_type=ProductImage.IMAGE,
                    placement=ProductImage.GALLERY,
                    remote_url=image.replace("w=900", "w=901"),
                    alt_text=f"{product.name} alternate",
                    sort_order=2,
                )
                ProductImage.objects.create(
                    product=product,
                    media_type=ProductImage.VIDEO,
                    placement=ProductImage.GALLERY,
                    video_url="https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
                    thumbnail_url=image,
                    alt_text=f"{product.name} texture video",
                    sort_order=3,
                )
                ProductImage.objects.create(
                    product=product,
                    media_type=ProductImage.IMAGE,
                    placement=ProductImage.BEFORE,
                    remote_url="https://images.unsplash.com/photo-1515377905703-c4788e51af15?auto=format&fit=crop&w=900&q=80",
                    alt_text=f"{product.name} before result",
                    sort_order=10,
                )
                ProductImage.objects.create(
                    product=product,
                    media_type=ProductImage.VIDEO,
                    placement=ProductImage.AFTER,
                    video_url="https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
                    thumbnail_url=image,
                    alt_text=f"{product.name} after result video",
                    sort_order=11,
                )
                if category_slug != "beauty-tools":
                    ProductVariant.objects.create(product=product, name="Size", value="Full size", sku=f"ANNA-{product_counter:04d}-FULL", stock=18)
                    ProductVariant.objects.create(product=product, name="Size", value="Travel", sku=f"ANNA-{product_counter:04d}-TRAVEL", stock=12, price_delta=Decimal("-150"))
                product_counter += 1

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

        self.stdout.write(self.style.SUCCESS("Anaacoss catalogue seeded with 150 products."))
