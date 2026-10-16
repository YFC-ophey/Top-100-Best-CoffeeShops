import json
from pathlib import Path

from src.country_centroids import UNKNOWN_COUNTRY, normalize_country
from src.geocoder import GeocodeResult, GooglePlacesGeocoder
from src.models import CoffeeShop


def _is_verified_pergamino_laureles_location(row: dict[str, object]) -> bool:
    # Pergamino publishes Cq 73 #34-65, while Google labels this same shop
    # Tv 34 #34-65. Its own directions link pins 6.2413562, -75.5961657:
    # https://co.pergamino.co/pages/tiendas/laureles
    return (
        row.get("name") == "Pergamino Café Laureles"
        and row.get("category") == "South America"
        and row.get("rank") == 38
        and "Cq 73 #34 - 65" in str(row.get("address") or "")
        and "Tv 34 #34 - 65" in str(row.get("formatted_address") or "")
        and row.get("lat") is not None
        and row.get("lng") is not None
        and abs(float(row["lat"]) - 6.2413562) < 0.0001
        and abs(float(row["lng"]) - (-75.5961657)) < 0.0001
    )


def _is_verified_exploradores_entrance(row: dict[str, object]) -> bool:
    # Exploradores' official locations page says the shop is at Av. Santa Fe
    # 596 and tells visitors to navigate to 601, which is the entrance. Keep
    # the owner-confirmed Google entrance pin even though the numbers differ.
    # https://www.exploradores.cafe/pages/ubicaciones
    return (
        row.get("name") == "Exploradores"
        and row.get("category") == "Top 100"
        and row.get("rank") == 87
        and "Santa Fé 596" in str(row.get("address") or "")
        and "Av. Santa Fe 601" in str(row.get("formatted_address") or "")
        and row.get("lat") is not None
        and row.get("lng") is not None
        and abs(float(row["lat"]) - 19.3554536) < 0.0001
        and abs(float(row["lng"]) - (-99.275689)) < 0.0001
    )


def test_no_place_id_shared_across_different_countries() -> None:
    data_path = Path(__file__).resolve().parent.parent / "data" / "current_list.json"
    rows = json.loads(data_path.read_text(encoding="utf-8"))

    place_to_countries: dict[str, set[str]] = {}
    for row in rows:
        place_id = str(row.get("place_id") or "").strip()
        if not place_id:
            continue
        normalized_country, unknown = normalize_country(str(row.get("country") or ""))
        country = normalized_country if not unknown else UNKNOWN_COUNTRY
        place_to_countries.setdefault(place_id, set()).add(country)

    offenders = {
        place_id: sorted(countries)
        for place_id, countries in place_to_countries.items()
        if len(countries) > 1
    }

    assert not offenders, f"place_id mapped to multiple countries: {offenders}"


def test_rank_71_little_victories_has_ottawa_coordinates() -> None:
    data_path = Path(__file__).resolve().parent.parent / "data" / "current_list.json"
    rows = json.loads(data_path.read_text(encoding="utf-8"))

    target = next(
        (
            row
            for row in rows
            if str(row.get("rank")) == "71"
            and str(row.get("category")) == "Top 100"
            and str(row.get("name")) == "Little Victories Coffee"
        ),
        None,
    )
    assert target is not None, "Expected rank 71 Little Victories Coffee row in dataset"

    lat = target.get("lat")
    lng = target.get("lng")
    assert lat is not None and lng is not None, "Rank 71 must not use centroid fallback coordinates"

    # Ottawa city bounds (approx): avoid regressions to western Canada fallback pins.
    assert 45.30 <= float(lat) <= 45.50
    assert -75.80 <= float(lng) <= -75.55


def test_geocoded_rows_match_shop_identity_rules() -> None:
    data_path = Path(__file__).resolve().parent.parent / "data" / "current_list.json"
    rows = json.loads(data_path.read_text(encoding="utf-8"))

    geocoder = GooglePlacesGeocoder("DUMMY")
    offenders: list[tuple[int, str, str]] = []

    for row in rows:
        if row.get("lat") is None or row.get("lng") is None:
            continue

        shop = CoffeeShop(**row)
        result = GeocodeResult(
            lat=float(row["lat"]),
            lng=float(row["lng"]),
            place_id=str(row.get("place_id") or ""),
            formatted_address=str(row.get("formatted_address") or ""),
        )
        if (
            not geocoder._result_matches_shop(shop, result)
            and not _is_verified_pergamino_laureles_location(row)
            and not _is_verified_exploradores_entrance(row)
        ):
            offenders.append((int(row.get("rank", 0)), str(row.get("category") or ""), str(row.get("name") or "")))

    assert not offenders, f"Geocode identity mismatch rows: {offenders}"
