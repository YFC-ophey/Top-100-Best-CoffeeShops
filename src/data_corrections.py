"""Source-backed corrections for ranking pages with conflicting location fields."""

from src.models import CoffeeShop


_VERIFIED_FIELDS: dict[tuple[str, int, str], dict[str, str]] = {
    (
        "South America",
        25,
        "Typica Café",
    ): {
        "city": "Cochabamba",
        "address": "El Prado, calle España, entre calles La Paz y Reza #661, Cochabamba, Bolivia",
    }
}


def apply_verified_shop_corrections(shops: list[CoffeeShop]) -> None:
    """Apply official shop-location details that resolve source-page conflicts."""
    for shop in shops:
        fields = _VERIFIED_FIELDS.get((shop.category, shop.rank, shop.name))
        if not fields:
            continue
        for field, value in fields.items():
            setattr(shop, field, value)
