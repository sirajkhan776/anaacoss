from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.catalog.models import Category, Product


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return ["home", "shop", "offers", "about", "contact", "faq"]

    def location(self, item):
        return reverse(item)


class CategorySitemap(Sitemap):
    priority = 0.7
    changefreq = "weekly"

    def items(self):
        return Category.objects.filter(parent__isnull=True)

    def location(self, item):
        return reverse("category", kwargs={"category_slug": item.slug})

    def lastmod(self, item):
        return item.updated_at


class ProductSitemap(Sitemap):
    priority = 0.9
    changefreq = "daily"

    def items(self):
        return Product.objects.visible().select_related("brand", "category")

    def lastmod(self, item):
        return item.updated_at
