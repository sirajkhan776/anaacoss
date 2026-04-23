# Anaacoss Luxury Cosmetics eCommerce

Production-oriented Django + DRF eCommerce starter for a premium beauty brand with JWT auth, dynamic cart/wishlist/coupon flows, responsive templates, and luxury UI assets.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_store
python manage.py createsuperuser
python manage.py runserver
```

The app defaults to SQLite in development if `DATABASE_URL` is not configured. Use `DJANGO_SQLITE_PATH` if your local folder does not allow SQLite journal writes. For PostgreSQL, create the database in `.env` and run migrations.

## Main URLs

- Site: `http://127.0.0.1:8000/`
- Admin: `http://127.0.0.1:8000/admin/`
- API: `http://127.0.0.1:8000/api/`
- JWT login: `POST /api/auth/login/`
- JWT refresh: `POST /api/auth/token/refresh/`

## Structure

- `apps.accounts`: custom user, profile, addresses, JWT auth endpoints
- `apps.catalog`: categories, brands, products, variants, images, reviews, search/filter APIs
- `apps.commerce`: cart, wishlist, coupons, checkout, orders
- `apps.content`: banners, testimonials, newsletter, informational content
- `templates`: progressive SPA-like pages using Fetch API
- `static/css/luxe.css`: responsive luxury visual system
- `static/js/storefront.js`: AJAX navigation, auth, cart, wishlist, coupon, checkout behavior
