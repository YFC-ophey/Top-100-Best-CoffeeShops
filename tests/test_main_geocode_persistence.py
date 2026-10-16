from src.main import _carry_forward_geocode
from src.models import CoffeeShop


def test_carry_forward_geocode_reuses_previous_fields() -> None:
    previous = [
        CoffeeShop(
            name="Onyx Coffee LAB",
            city="Rogers",
            country="USA",
            rank=1,
            category="Top 100",
            source_url="https://theworlds100bestcoffeeshops.com/locales/onyx-coffee-lab/",
            lat=36.332,
            lng=-94.118,
            place_id="abc123",
            formatted_address="101 E Walnut Ave Rogers, AR 72756, USA",
        )
    ]
    current = [
        CoffeeShop(
            name="Onyx Coffee LAB",
            city="Rogers",
            country="USA",
            rank=1,
            category="Top 100",
            source_url="https://theworlds100bestcoffeeshops.com/locales/onyx-coffee-lab/",
            address="101 E Walnut Ave, Rogers, AR 72756, USA",
            lat=None,
            lng=None,
            place_id=None,
            formatted_address=None,
        )
    ]

    updated = _carry_forward_geocode(previous, current)

    assert updated[0].place_id == "abc123"
    assert updated[0].lat == 36.332
    assert updated[0].lng == -94.118
    assert updated[0].formatted_address == "101 E Walnut Ave Rogers, AR 72756, USA"


def test_carry_forward_reuses_verified_pin_across_collections_for_exact_location() -> None:
    previous = [
        CoffeeShop(
            name="Coffeewerk + Press",
            city="Galway",
            country="Ireland",
            rank=32,
            category="Top 100",
            source_url="https://example.com/world/coffeewerk",
            address="4 Quay St, Galway, Ireland",
            lat=53.2713459,
            lng=-9.0539731,
            place_id="galway-shop",
            formatted_address="4 Quay St, Galway, H91 E2K6, Ireland",
        )
    ]
    current = [
        CoffeeShop(
            name="Coffeewerk + Press",
            city="Galway",
            country="Ireland",
            rank=5,
            category="Europe",
            source_url="https://example.com/europe/coffeewerk",
            address="4 Quay St, Galway, Ireland",
        )
    ]

    updated = _carry_forward_geocode(previous, current)

    assert updated[0].lat == 53.2713459
    assert updated[0].lng == -9.0539731
    assert updated[0].place_id == "galway-shop"
    assert updated[0].formatted_address == "4 Quay St, Galway, H91 E2K6, Ireland"


def test_carry_forward_does_not_share_pin_across_different_addresses() -> None:
    previous = [
        CoffeeShop(
            name="Same Coffee",
            city="Galway",
            country="Ireland",
            rank=32,
            category="Top 100",
            address="4 Quay St, Galway, Ireland",
            lat=53.2713459,
            lng=-9.0539731,
            place_id="galway-shop",
            formatted_address="4 Quay St, Galway, H91 E2K6, Ireland",
        )
    ]
    current = [
        CoffeeShop(
            name="Same Coffee",
            city="Galway",
            country="Ireland",
            rank=5,
            category="Europe",
            address="8 Quay St, Galway, Ireland",
        )
    ]

    updated = _carry_forward_geocode(previous, current)

    assert updated[0].lat is None
    assert updated[0].lng is None
    assert updated[0].place_id is None


def test_carry_forward_skips_conflicting_cross_collection_pins() -> None:
    previous = [
        CoffeeShop(
            name="Same Coffee",
            city="Galway",
            country="Ireland",
            rank=32,
            category="Top 100",
            address="4 Quay St, Galway, Ireland",
            lat=53.2713459,
            lng=-9.0539731,
            place_id="galway-shop-a",
            formatted_address="4 Quay St, Galway, H91 E2K6, Ireland",
        ),
        CoffeeShop(
            name="Same Coffee",
            city="Galway",
            country="Ireland",
            rank=10,
            category="South America",
            address="4 Quay St, Galway, Ireland",
            lat=53.272,
            lng=-9.054,
            place_id="galway-shop-b",
            formatted_address="4 Quay St, Galway, H91 E2K6, Ireland",
        ),
    ]
    current = [
        CoffeeShop(
            name="Same Coffee",
            city="Galway",
            country="Ireland",
            rank=5,
            category="Europe",
            address="4 Quay St, Galway, Ireland",
        )
    ]

    updated = _carry_forward_geocode(previous, current)

    assert updated[0].lat is None
    assert updated[0].lng is None
    assert updated[0].place_id is None


def test_carry_forward_keeps_city_and_address_when_detail_fetch_failed() -> None:
    previous = [
        CoffeeShop(
            name="Tim Wendelboe",
            city="Oslo",
            country="Norway",
            rank=2,
            category="Top 100",
            source_url="https://theworlds100bestcoffeeshops.com/locales/tim-wendelboe/",
            address="Grüners Gate 1, 0552 Oslo, Norway",
        )
    ]
    current = [
        CoffeeShop(
            name="Tim Wendelboe",
            city="",
            country="Norway",
            rank=2,
            category="Top 100",
            source_url="https://theworlds100bestcoffeeshops.com/locales/tim-wendelboe/",
            address=None,
        )
    ]

    updated = _carry_forward_geocode(previous, current)

    assert updated[0].city == "Oslo"
    assert updated[0].address == "Grüners Gate 1, 0552 Oslo, Norway"


def test_carry_forward_does_not_overwrite_a_fresh_city() -> None:
    previous = [
        CoffeeShop(
            name="Tim Wendelboe",
            city="Oslo",
            country="Norway",
            rank=2,
            category="Top 100",
            source_url="https://theworlds100bestcoffeeshops.com/locales/tim-wendelboe/",
        )
    ]
    current = [
        CoffeeShop(
            name="Tim Wendelboe",
            city="Grünerløkka",
            country="Norway",
            rank=2,
            category="Top 100",
            source_url="https://theworlds100bestcoffeeshops.com/locales/tim-wendelboe/",
        )
    ]

    updated = _carry_forward_geocode(previous, current)

    assert updated[0].city == "Grünerløkka"
