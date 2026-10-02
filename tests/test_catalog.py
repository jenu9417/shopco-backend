API = "/api/v1"


async def _setup(client, h):
    brand_a = (await client.post(f"{API}/admin/brands", headers=h, json={"name": "Zara"})).json()
    brand_b = (await client.post(f"{API}/admin/brands", headers=h, json={"name": "Gucci"})).json()
    cat = (await client.post(f"{API}/admin/categories", headers=h, json={"name": "T-shirts"})).json()
    return brand_a, brand_b, cat


def _product(title, brand, cat, price, *, compare_at=None, status="published", prefix="X", sizes=("M", "L")):
    return {
        "title": title,
        "brand_id": brand["id"],
        "category_ids": [cat["id"]],
        "status": status,
        "images": [{"url": "https://img.example/a.jpg"}],
        "variants": [
            {"sku": f"{prefix}-{s}", "size": s, "color": "Black", "price": price,
             "compare_at_price": compare_at, "stock_quantity": 5 if s == "M" else 0}
            for s in sizes
        ],
    }


async def test_admin_endpoints_require_staff(client, customer_headers):
    assert (await client.get(f"{API}/admin/products")).status_code == 401
    r = await client.get(f"{API}/admin/products", headers=customer_headers)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "insufficient_permissions"


async def test_create_and_fetch_product(client, admin_headers):
    zara, _, cat = await _setup(client, admin_headers)
    r = await client.post(
        f"{API}/admin/products", headers=admin_headers,
        json=_product("Classic Tee", zara, cat, 99900, compare_at=149900, prefix="TEE"),
    )
    assert r.status_code == 201, r.text
    admin_view = r.json()
    assert admin_view["slug"] == "classic-tee"
    assert admin_view["thumbnail_url"] == "https://img.example/a.jpg"

    d = (await client.get(f"{API}/store/products/classic-tee")).json()
    assert d["price"] == 99900 and d["compare_at_price"] == 149900
    assert d["discount_percent"] == 33 and d["in_stock"] is True
    assert d["sizes"] == ["M", "L"] and d["brand"]["slug"] == "zara"
    assert "stock_quantity" not in d["variants"][0]  # hidden on the storefront


async def test_duplicate_title_gets_unique_slug_and_duplicate_sku_conflicts(client, admin_headers):
    zara, _, cat = await _setup(client, admin_headers)
    await client.post(f"{API}/admin/products", headers=admin_headers, json=_product("Tee", zara, cat, 1000, prefix="A"))
    r2 = await client.post(f"{API}/admin/products", headers=admin_headers, json=_product("Tee", zara, cat, 1000, prefix="B"))
    assert r2.json()["slug"] == "tee-2"
    r3 = await client.post(f"{API}/admin/products", headers=admin_headers, json=_product("Other", zara, cat, 1000, prefix="A"))
    assert r3.status_code == 409 and r3.json()["error"]["code"] == "sku_already_exists"


async def test_drafts_hidden_from_storefront(client, admin_headers):
    zara, _, cat = await _setup(client, admin_headers)
    await client.post(f"{API}/admin/products", headers=admin_headers,
                      json=_product("Secret", zara, cat, 1000, status="draft", prefix="S"))
    assert (await client.get(f"{API}/store/products")).json()["total"] == 0
    assert (await client.get(f"{API}/store/products/secret")).status_code == 404
    assert (await client.get(f"{API}/admin/products", headers=admin_headers)).json()["total"] == 1


async def test_cannot_publish_without_variants(client, admin_headers):
    r = await client.post(f"{API}/admin/products", headers=admin_headers,
                          json={"title": "Empty", "status": "published"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "product_not_publishable"


async def test_filters_sorting_and_pagination(client, admin_headers):
    zara, gucci, cat = await _setup(client, admin_headers)
    await client.post(f"{API}/admin/products", headers=admin_headers, json=_product("Classic Tee", zara, cat, 99900, prefix="A"))
    await client.post(f"{API}/admin/products", headers=admin_headers, json=_product("Fancy Shirt", gucci, cat, 250000, prefix="B", sizes=("XL",)))

    def titles(r):
        return [i["title"] for i in r.json()["items"]]

    assert titles(await client.get(f"{API}/store/products?sort=price_desc")) == ["Fancy Shirt", "Classic Tee"]
    assert titles(await client.get(f"{API}/store/products?sort=price_asc")) == ["Classic Tee", "Fancy Shirt"]
    assert titles(await client.get(f"{API}/store/products?min_price=100000")) == ["Fancy Shirt"]
    assert titles(await client.get(f"{API}/store/products?brand=zara")) == ["Classic Tee"]
    assert titles(await client.get(f"{API}/store/products?size=xl")) == ["Fancy Shirt"]
    assert titles(await client.get(f"{API}/store/products?q=shirt")) == ["Fancy Shirt"]
    assert titles(await client.get(f"{API}/store/products?category=t-shirts&brand=zara&brand=gucci")) != []

    page = (await client.get(f"{API}/store/products?page_size=1&page=2&sort=price_asc")).json()
    assert page["total"] == 2 and page["pages"] == 2 and page["items"][0]["title"] == "Fancy Shirt"

    bad = await client.get(f"{API}/store/products?min_price=10&max_price=5")
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_price_range"


async def test_update_variant_and_archive(client, admin_headers):
    zara, _, cat = await _setup(client, admin_headers)
    p = (await client.post(f"{API}/admin/products", headers=admin_headers,
                           json=_product("Tee", zara, cat, 1000, prefix="U", sizes=("M",)))).json()
    vid = p["variants"][0]["id"]

    r = await client.patch(f"{API}/admin/variants/{vid}", headers=admin_headers, json={"price": 1500, "stock_quantity": 9})
    assert r.status_code == 200 and r.json()["price"] == 1500 and r.json()["stock_quantity"] == 9

    # deactivating the only variant of a published product is refused
    r = await client.patch(f"{API}/admin/variants/{vid}", headers=admin_headers, json={"is_active": False})
    assert r.status_code == 409

    assert (await client.delete(f"{API}/admin/products/{p['id']}", headers=admin_headers)).status_code == 204
    assert (await client.get(f"{API}/store/products/tee")).status_code == 404


async def test_categories_and_brands_public_lists(client, admin_headers):
    _, _, cat = await _setup(client, admin_headers)
    cats = (await client.get(f"{API}/store/categories")).json()
    assert [c["slug"] for c in cats] == ["t-shirts"]
    assert {b["slug"] for b in (await client.get(f"{API}/store/brands")).json()} == {"zara", "gucci"}
    assert (await client.get(f"{API}/store/stats")).json() == {"products": 0, "brands": 2}

    dup = await client.post(f"{API}/admin/brands", headers=admin_headers, json={"name": "zara"})
    assert dup.status_code == 409
