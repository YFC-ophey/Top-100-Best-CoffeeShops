import json
from pathlib import Path

from src.category_utils import normalize_category, normalize_edition_year
from src.models import CoffeeShop


def load_previous_state(path: Path) -> list[CoffeeShop]:
    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    return [CoffeeShop(**item) for item in payload]


def has_shop_changes(previous: list[CoffeeShop], current: list[CoffeeShop]) -> bool:
    return _canonical(previous) != _canonical(current)


def _canonical(shops: list[CoffeeShop]) -> list[tuple[int, str, int, str, str, str]]:
    normalized = [
        (
            normalize_edition_year(shop.edition_year),
            normalize_category(shop.category),
            shop.rank,
            shop.name.strip().casefold(),
            shop.city.strip().casefold(),
            shop.country.strip().casefold(),
        )
        for shop in shops
    ]
    return sorted(normalized)
