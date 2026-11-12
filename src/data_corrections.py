"""Source-backed corrections for ranking pages with conflicting location fields."""

from src.models import CoffeeShop


_VERIFIED_FIELDS: dict[tuple[str, int, str], dict[str, str | float | None]] = {
    (
        "South America",
        25,
        "Typica Café",
    ): {
        "city": "Cochabamba",
        "address": "El Prado, calle España, entre calles La Paz y Reza #661, Cochabamba, Bolivia",
    },
    ("Asia-Pacific", 13, "Categorique"): {
        # Same department-store branch and floor; include the street number so
        # strict address matching can retain its pin on the next weekly sync.
        "address": "176 Sinbanpo-ro, 11th Floor, Shinsegae Department Store Gangnam, Seocho District, Seoul, South Korea",
    },
    ("Asia-Pacific", 46, "Ignis"): {"country": "Japan"},
    ("Asia-Pacific", 54, "Le J’ cafe"): {
        # lejcafe.com publishes 51A Yersin; Maps calls its entrance Hẻm 51.
        "address": "51A Yersin (Hẻm 51 Yersin), Xuân Hương - Đà Lạt, Lâm Đồng, Vietnam",
    },
    # Exact storefronts cross-checked against Amap, 360 Maps and the published
    # street numbers. These are GCJ-02 positions for the Google China road map,
    # not WGS84 coordinates copied from an OSM map. Evidence: docs/location-audits/.
    ("Asia-Pacific", 18, "Coffee Enough"): {
        "lat": 31.233511, "lng": 121.463432, "place_id": None,
        "formatted_address": "549-4 West Beijing Rd, Shanghai, China",
    },
    ("Asia-Pacific", 48, "Blacksheep Espresso"): {
        "city": "Shanghai", "lat": 31.215375, "lng": 121.461899,
        "place_id": None,
        "formatted_address": "124 Maoming South Rd, Huangpu District, Shanghai, China",
    },
}


def apply_verified_shop_corrections(shops: list[CoffeeShop]) -> None:
    """Apply official shop-location details that resolve source-page conflicts."""
    for shop in shops:
        # Keep the same Hong Kong business consistently grouped across lists.
        if shop.name == "Espresso Alchemy" and "Hong Kong" in (shop.address or ""):
            shop.country = "Hong Kong"
        fields = _VERIFIED_FIELDS.get((shop.category, shop.rank, shop.name))
        if not fields:
            continue
        for field, value in fields.items():
            setattr(shop, field, value)
