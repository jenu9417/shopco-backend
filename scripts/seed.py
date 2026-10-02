"""Idempotent seed: admin user + demo catalog that mirrors the SHOP.CO homepage.

    python -m scripts.seed
Images are placeholders (placehold.co) - replace with real assets / uploads.
"""

import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.modules.auth.models import Role, User
from app.modules.catalog.models import (
    Brand,
    Category,
    Product,
    ProductImage,
    ProductStatus,
    ProductVariant,
)

CATEGORIES = [("T-shirts", "t-shirts"), ("Shorts", "shorts"), ("Shirts", "shirts"),
              ("Hoodie", "hoodie"), ("Jeans", "jeans")]
BRANDS = [("Versace", "versace"), ("Zara", "zara"), ("Gucci", "gucci"),
          ("Prada", "prada"), ("Calvin Klein", "calvin-klein")]

# (title, slug, brand_slug, category_slug, price_rupees, mrp_rupees|None, colors, rating, sales)
PRODUCTS = [
    ("T-shirt with Tape Details", "t-shirt-with-tape-details", "zara", "t-shirts", 1200, None, ["Black", "White"], 4.5, 320),
    ("Skinny Fit Jeans", "skinny-fit-jeans", "calvin-klein", "jeans", 2400, 3000, ["Blue"], 3.5, 210),
    ("Checkered Shirt", "checkered-shirt", "gucci", "shirts", 1800, None, ["Red"], 4.5, 180),
    ("Sleeve Striped T-shirt", "sleeve-striped-t-shirt", "versace", "t-shirts", 1300, 1600, ["Orange"], 4.5, 150),
    ("Vertical Striped Shirt", "vertical-striped-shirt", "prada", "shirts", 2120, 2320, ["Green"], 5.0, 400),
    ("Courage Graphic T-shirt", "courage-graphic-t-shirt", "zara", "t-shirts", 1450, None, ["Orange"], 4.0, 90),
    ("Loose Fit Bermuda Shorts", "loose-fit-bermuda-shorts", "calvin-klein", "shorts", 8000, None, ["Blue"], 3.0, 60),
    ("Hooded Zip Jacket", "hooded-zip-jacket", "versace", "hoodie", 3500, 4200, ["Black", "Grey"], 4.5, 275),
]
SIZES = ["S", "M", "L", "XL"]


async def main() -> None:
    s = get_settings()
    async with SessionLocal() as db:
        if not (await db.scalars(select(User).where(User.email == s.seed_admin_email))).first():
            db.add(User(email=s.seed_admin_email, password_hash=hash_password(s.seed_admin_password),
                        first_name="Admin", role=Role.admin))

        cats, brands = {}, {}
        for name, slug in CATEGORIES:
            c = (await db.scalars(select(Category).where(Category.slug == slug))).first()
            if not c:
                c = Category(name=name, slug=slug)
                db.add(c)
            cats[slug] = c
        for name, slug in BRANDS:
            b = (await db.scalars(select(Brand).where(Brand.slug == slug))).first()
            if not b:
                b = Brand(name=name, slug=slug)
                db.add(b)
            brands[slug] = b
        await db.flush()

        for title, slug, brand, cat, price, mrp, colors, rating, sales in PRODUCTS:
            if (await db.scalars(select(Product).where(Product.slug == slug))).first():
                continue
            img = f"https://placehold.co/600x800?text={slug}"
            p = Product(
                title=title, slug=slug, status=ProductStatus.published.value,
                description=f"{title} - demo product.", brand_id=brands[brand].id,
                thumbnail_url=img, hsn_code="6109", tax_rate_bps=1200,
                rating_avg=rating, rating_count=int(sales / 3), sales_count=sales,
            )
            p.categories = [cats[cat]]
            p.images = [ProductImage(url=img, alt=title, position=0)]
            variants, pos = [], 0
            for color in colors:
                for size in SIZES:
                    variants.append(ProductVariant(
                        sku=f"{slug[:12]}-{color[:3]}-{size}".upper(), title=f"{size} / {color}",
                        size=size, color=color, price=price * 100,
                        compare_at_price=mrp * 100 if mrp else None,
                        stock_quantity=25, position=pos))
                    pos += 1
            p.variants = variants
            db.add(p)

        await db.commit()
    await engine.dispose()
    print(f"Seeded. Admin login: {s.seed_admin_email} / {s.seed_admin_password}  (change it!)")


if __name__ == "__main__":
    asyncio.run(main())
