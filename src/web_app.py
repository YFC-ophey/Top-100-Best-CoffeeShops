from __future__ import annotations

import csv
from collections import Counter, defaultdict
import html
from functools import lru_cache
import os
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates

from src.category_utils import (
    SOUTH_AMERICA_CATEGORY,
    TOP_100_CATEGORY,
    normalize_category,
    normalize_edition_year,
)
from src.country_centroids import (
    COUNTRY_ALIASES,
    COUNTRY_CENTROIDS,
    UNKNOWN_COUNTRY,
    country_base_color,
    country_centroid,
    normalize_country,
)
from src.models import CoffeeShop
from src.state import load_previous_state

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_FILE = BASE_DIR / "data" / "current_list.json"
DEFAULT_CSV_FILE = BASE_DIR / "output" / "coffee_shops.csv"
DEFAULT_KML_FILE = BASE_DIR / "output" / "coffee_shops.kml"
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

RANK_BANDS = [
    {"key": "Top 20", "label": "Top 20", "min": 1, "max": 20},
    {"key": "Top 50", "label": "Top 50", "min": 21, "max": 50},
    {"key": "The Rest", "label": "The Rest", "min": 51, "max": 100},
]

_STREET_WORDS = {
    "st",
    "street",
    "rd",
    "road",
    "ave",
    "avenue",
    "av",
    "calle",
    "carrer",
    "r",
    "jr",
    "lane",
    "ln",
    "highway",
    "hwy",
    "shop",
    "unit",
    "local",
    "bldg",
    "building",
    "warehouse",
    "edificio",
    "cll",
    "cra",
}

_CITY_CANONICAL_ALIASES = {
    "cdad autonoma de buenos aires": "Buenos Aires",
    "ciudad autonoma de buenos aires": "Buenos Aires",
    "ciudad de buenos aires": "Buenos Aires",
    "capital federal": "Buenos Aires",
}

_SUBREGION_EXACT_LABELS = {
    "magallanes y la antartica chilena",
}

_SHOP_FIELD_OVERRIDES: dict[tuple[str, int], dict[str, str]] = {
    (
        TOP_100_CATEGORY,
        68,
    ): {
        "name": "Azure The Coffee Company",
        "city": "Muscat",
        "country": "Oman",
        "formatted_address": "Multiple locations, Muscat, Oman",
    }
}

_ADDRESS_FILE_SPECS = (
    ("top 100 coffee shops address.csv", TOP_100_CATEGORY),
    ("south america coffee shops address.csv", SOUTH_AMERICA_CATEGORY),
)

def create_app(data_file: Path, csv_file: Path, kml_file: Path) -> FastAPI:
    app = FastAPI(title="Top100BestCoffeeShops Preview")
    app.state.data_file = data_file
    app.state.csv_file = csv_file
    app.state.kml_file = kml_file

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def home(request: Request):
        shops = _load_shops(app.state.data_file)
        normalized_shops = sorted(shops, key=lambda value: (value.rank, value.category, value.name))

        category_counts = Counter(shop.category for shop in normalized_shops)
        top_100_links = _build_ordered_links(normalized_shops, TOP_100_CATEGORY)
        south_america_links = _build_ordered_links(normalized_shops, SOUTH_AMERICA_CATEGORY)

        overview_shops, data_quality = _build_overview_shops(normalized_shops)
        overview_countries = _build_overview_countries(overview_shops)
        overview_filters = _build_overview_filters(overview_shops, overview_countries)

        context = {
            "request": request,
            "shops": normalized_shops,
            "total_shops": len(normalized_shops),
            "category_counts": dict(sorted(category_counts.items())),
            "csv_available": app.state.csv_file.exists(),
            "kml_available": app.state.kml_file.exists(),
            "csv_url": "/artifacts/csv",
            "kml_url": "/artifacts/kml",
            "top_100_links": top_100_links,
            "south_america_links": south_america_links,
            "south_links": south_america_links,
            "overview_shops": overview_shops,
            "overview_countries": overview_countries,
            "overview_filters": overview_filters,
            "data_quality": data_quality,
            "google_maps_js_api_key": _google_maps_js_key(),
        }
        return TEMPLATES.TemplateResponse(request=request, name="index.html", context=context)

    @app.get("/artifacts/{artifact_name}")
    def artifact(artifact_name: str):
        paths = {"csv": app.state.csv_file, "kml": app.state.kml_file}
        target = paths.get(artifact_name)
        if target is None or not target.exists():
            raise HTTPException(status_code=404, detail="Artifact not found")
        media_type = "text/csv" if artifact_name == "csv" else "application/vnd.google-earth.kml+xml"
        return FileResponse(path=target, media_type=media_type, filename=target.name)

    @app.get("/map-style-inspo.png")
    def map_style_inspo():
        image_path = BASE_DIR / "map-style-inspo.png"
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Map style image not found")
        return FileResponse(path=image_path, media_type="image/png", filename=image_path.name)

    return app


def _google_maps_js_key() -> str:
    for env_key in ("GOOGLE_MAPS_JS_API_KEY", "GOOGLE_MAPS_API_KEY"):
        env_value = os.getenv(env_key, "").strip()
        if env_value:
            return env_value

    env_candidates = [BASE_DIR / ".env"]
    if BASE_DIR.parent.name == ".worktrees":
        env_candidates.append(BASE_DIR.parent.parent / ".env")

    for env_path in env_candidates:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("#") or "=" not in cleaned:
                continue
            key, value = cleaned.split("=", 1)
            if key.strip() in {"GOOGLE_MAPS_JS_API_KEY", "GOOGLE_MAPS_API_KEY"}:
                return value.strip().strip('"').strip("'")
    return ""


def _load_shops(data_file: Path) -> list[CoffeeShop]:
    if not data_file.exists():
        return []

    shops = load_previous_state(data_file)
    for shop in shops:
        shop.category = normalize_category(shop.category)
        shop.edition_year = normalize_edition_year(shop.edition_year)
        shop.name = _normalize_shop_text(shop.name)
        shop.city = _normalize_shop_text(shop.city)
        shop.country = _normalize_shop_text(shop.country)
        shop.address = _normalize_shop_text(shop.address)
        shop.formatted_address = _normalize_shop_text(shop.formatted_address)
        shop.source_url = _normalize_shop_text(shop.source_url)
        _apply_shop_override(shop)
    _apply_address_overrides(shops)
    return shops


def _apply_address_overrides(shops: list[CoffeeShop]) -> None:
    exact_matches = _load_address_overrides()
    if not exact_matches:
        return

    for shop in shops:
        if (shop.formatted_address or "").strip():
            continue
        category = normalize_category(shop.category)
        key = _address_match_key(shop.rank, shop.name, category)
        resolved = exact_matches.get(key)
        if not resolved:
            continue
        shop.formatted_address = resolved
        if not (shop.address or "").strip():
            shop.address = resolved


@lru_cache(maxsize=1)
def _load_address_overrides() -> dict[str, str]:
    exact_matches: dict[str, str] = {}
    seen_paths: set[Path] = set()

    for output_dir in _candidate_output_dirs():
        for filename, category in _ADDRESS_FILE_SPECS:
            path = output_dir / filename
            if path in seen_paths or not path.exists():
                continue
            seen_paths.add(path)

            try:
                with path.open(encoding="utf-8", newline="") as handle:
                    for row in csv.DictReader(handle):
                        rank_raw = (row.get("Rank") or "").strip()
                        name_raw = _normalize_shop_text(row.get("Coffee Shop") or "")
                        address_raw = _normalize_shop_text(row.get("Address") or "")
                        if not rank_raw or not name_raw or not address_raw:
                            continue
                        try:
                            rank = int(rank_raw)
                        except ValueError:
                            continue

                        exact_matches[_address_match_key(rank, name_raw, category)] = address_raw
            except OSError:
                continue

    return exact_matches


def _candidate_output_dirs() -> list[Path]:
    candidates: list[Path] = [BASE_DIR / "output"]
    if BASE_DIR.parent.name == ".worktrees":
        candidates.append(BASE_DIR.parent.parent / "output")
    return candidates


def _address_match_key(rank: int, name: str, category: str) -> str:
    normalized = unicodedata.normalize("NFKD", _normalize_shop_text(name).casefold())
    ascii_name = "".join(char for char in normalized if not unicodedata.combining(char))
    cleaned_name = re.sub(r"\W+", "", ascii_name)
    return f"{normalize_category(category)}::{int(rank)}::{cleaned_name}"


def _normalize_shop_text(value: str | None) -> str:
    if value is None:
        return ""
    unescaped = html.unescape(str(value))
    collapsed = re.sub(r"\s+", " ", unescaped).strip()
    return collapsed


def _apply_shop_override(shop: CoffeeShop) -> None:
    override = _SHOP_FIELD_OVERRIDES.get((normalize_category(shop.category), int(shop.rank)))
    if not override:
        return
    for key, value in override.items():
        setattr(shop, key, value)


def _build_ordered_links(shops: list[CoffeeShop], category: str) -> list[dict[str, str]]:
    filtered = [shop for shop in shops if normalize_category(shop.category) == category]
    ordered = sorted(filtered, key=lambda value: (value.rank, value.name))
    return [
        {
            "label": f"{shop.rank}. {shop.name}",
            "url": _google_maps_link(shop),
        }
        for shop in ordered
    ]


def _google_maps_link(shop: CoffeeShop) -> str:
    place_id = _normalize_shop_text(shop.place_id)
    if place_id:
        return f"https://www.google.com/maps/place/?{urlencode({'q': f'place_id:{place_id}'})}"

    if shop.lat is not None and shop.lng is not None:
        coords = f"{_format_coordinate(shop.lat)},{_format_coordinate(shop.lng)}"
        return f"https://www.google.com/maps/search/?{urlencode({'api': '1', 'query': coords})}"

    query = _best_map_query_text(shop)
    params: dict[str, str] = {"api": "1", "query": query}
    return f"https://www.google.com/maps/search/?{urlencode(params)}"


def _mobile_maps_link(shop: CoffeeShop) -> str:
    destination = _mobile_destination_text(shop)
    return f"https://www.google.com/maps/dir/?{urlencode({'api': '1', 'destination': destination})}"


def _format_coordinate(value: float) -> str:
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def _mobile_destination_text(shop: CoffeeShop) -> str:
    name = _normalize_shop_text(shop.name)
    formatted_address = _sanitize_map_query((shop.formatted_address or "").strip(), shop.country)
    address = _sanitize_map_query((shop.address or "").strip(), shop.country)
    location = formatted_address or address or _best_map_query_text(shop)

    if not name:
        return location
    if location.casefold() == name.casefold():
        return name
    if location.casefold().startswith(f"{name.casefold()},"):
        return location
    return f"{name}, {location}"


def _best_map_query_text(shop: CoffeeShop) -> str:
    formatted_address = _sanitize_map_query((shop.formatted_address or "").strip(), shop.country)
    if formatted_address:
        return formatted_address

    address = _sanitize_map_query((shop.address or "").strip(), shop.country)
    if address:
        return address

    name = _normalize_shop_text(shop.name)
    city = _normalize_shop_text(shop.city)

    country_value, _ = normalize_country(shop.country)
    country = country_value if country_value and country_value != UNKNOWN_COUNTRY else _normalize_shop_text(shop.country)

    query = ""
    if city:
        query = ", ".join(part for part in [name, city, country] if part)
    elif country:
        query = ", ".join(part for part in [name, country] if part)
    else:
        query = name
    return _sanitize_map_query(query, country) or (name or "Coffee shop")


def _sanitize_map_query(text: str, country: str | None = None) -> str:
    cleaned = _normalize_shop_text(text)
    if not cleaned:
        return ""
    cleaned = re.sub(r"\bway number:\s*\d+\s*building number:\s*\d+\s*,?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bbuilding number:\s*\d+\s*,?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bunknown\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
    cleaned = re.sub(r"(,\s*){2,}", ", ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,")
    country_norm = _normalize_text_label(country or "")
    if country_norm:
        tokens = [token.strip() for token in cleaned.split(",") if token.strip()]
        deduped: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            normalized = _normalize_text_label(token)
            if not normalized:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(token)
        cleaned = ", ".join(deduped).strip(" ,")
    return cleaned


def _city_from_shop(shop: CoffeeShop, country_normalized: str) -> str:
    for address in (shop.formatted_address, shop.address):
        derived = _city_from_address(address, country_normalized)
        if derived:
            return derived

    explicit_city_raw = (shop.city or "").strip()
    explicit_city = _clean_city_candidate(explicit_city_raw)
    if explicit_city and _is_valid_explicit_city(explicit_city_raw, explicit_city):
        return explicit_city

    if explicit_city and (_looks_city_like(explicit_city) or _looks_city_acronym(explicit_city)):
        return explicit_city
    return ""


def _city_from_address(address: str | None, country_normalized: str) -> str:
    raw = html.unescape((address or "").strip())
    if not raw:
        return ""

    tokens = [token.strip() for token in re.split(r",| - ", raw) if token.strip()]
    if not tokens:
        return ""

    while tokens and _looks_like_country_label(tokens[-1], country_normalized):
        tokens.pop()
    if not tokens:
        return ""

    candidates: list[tuple[int, str, str]] = []
    for index in range(len(tokens) - 1, -1, -1):
        raw_token = tokens[index]
        candidate = _clean_city_candidate(raw_token)
        if candidate:
            candidates.append((index, raw_token, candidate))

    if not candidates:
        return ""

    for _, raw_token, candidate in candidates:
        if _looks_explicit_city_label(raw_token, candidate):
            return candidate

    for _, raw_token, candidate in candidates:
        if not _looks_street_like(raw_token) and not _looks_subregion_like(candidate):
            return candidate

    for _, raw_token, candidate in candidates:
        if not _looks_street_like(raw_token):
            return candidate

    return candidates[0][2]


def _clean_city_candidate(token: str) -> str:
    value = token.strip(" -")
    if not value:
        return ""

    value = re.sub(r"^[A-Z0-9]{4,8}\+[A-Z0-9]{2,4}\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\bD\d{1,2}\s*[A-Z0-9]{2,5}\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^[A-Za-z]?\d{3,6}(?:-\d{2,6})?\s+", "", value)
    value = re.sub(r"\s+[A-Z]{2,4}\s+\d{3,6}$", "", value)
    value = re.sub(r"\s+[A-Z]\d[A-Z]\s?\d[A-Z]\d$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\b\d{3,6}(?:-\d{2,6})?\b", "", value).strip(" -")
    value = re.sub(r"\s{2,}", " ", value).strip()
    if not value:
        return ""

    words = re.findall(r"[A-Za-zÀ-ÿ'.-]+", value)
    lowered_words = [word.casefold().strip(".") for word in words]
    street_indexes = [idx for idx, word in enumerate(lowered_words) if word in _STREET_WORDS]
    if street_indexes:
        tail = [word for word in words[street_indexes[-1] + 1 :] if len(word) > 1]
        if tail:
            value = " ".join(tail[-3:]).strip()

    if any(char.isdigit() for char in value):
        words = re.findall(r"[A-Za-zÀ-ÿ'.-]+", value)
        if words:
            value = " ".join(words[-2:]).strip()
        else:
            return ""

    if not re.search(r"[A-Za-zÀ-ÿ]", value):
        return ""

    lowered = value.casefold()
    if lowered in {"st", "rd", "ave", "unit", "local", "warehouse", "building"}:
        return ""
    if len(value) <= 2 and value.isupper():
        return ""
    return _canonical_city_label(value)


def _canonical_city_label(value: str) -> str:
    alias = _CITY_CANONICAL_ALIASES.get(_normalize_text_label(value))
    return alias or value


def _looks_street_like(value: str) -> bool:
    words = [word.casefold().strip(".") for word in re.findall(r"[A-Za-zÀ-ÿ'.-]+", value)]
    return any(word in _STREET_WORDS for word in words)


def _looks_city_like(value: str) -> bool:
    words = re.findall(r"[A-Za-zÀ-ÿ'.-]+", value)
    if not words:
        return False
    if not any(any(char.islower() for char in word) for word in words):
        return False
    if all(word.isupper() and len(word) <= 4 for word in words):
        return False
    if len(words) == 1:
        return len(words[0]) >= 3
    return any(len(word) >= 3 for word in words)


def _looks_city_acronym(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{3,5}", value.strip()))


def _is_valid_explicit_city(raw_value: str, cleaned_value: str) -> bool:
    if any(symbol in raw_value for symbol in ("[", "]", "<", ">", "{", "}")):
        return False
    if _looks_street_like(raw_value):
        return False
    if _looks_subregion_like(cleaned_value):
        return False
    if len(cleaned_value) > 34 or cleaned_value.count(" ") > 3:
        return False
    return _looks_city_like(cleaned_value) or _looks_city_acronym(cleaned_value)


def _looks_explicit_city_label(raw_token: str, candidate: str) -> bool:
    if _looks_street_like(raw_token):
        return False
    normalized = _normalize_text_label(candidate)
    return bool(re.search(r"\bcity\b|\bciudad\b|\bcidade\b", normalized))


def _looks_subregion_like(value: str) -> bool:
    normalized = _normalize_text_label(value)
    if normalized in _SUBREGION_EXACT_LABELS:
        return True
    return bool(
        re.search(
            r"\bregion\b|\bprovince\b|\bstate\b|\bdistrict\b|\bcounty\b|\bdepartamento\b|\bdepartment\b|\bprefecture\b|\bautonoma\b|\bmetropolitana\b|\bterritory\b|\bgovernorate\b",
            normalized,
        )
    )


def _looks_like_country_label(value: str, country_normalized: str) -> bool:
    normalized = _normalize_text_label(value)
    if not normalized:
        return False

    known_country_labels = set(_known_country_labels())
    known_country_labels.add(_normalize_text_label(country_normalized))
    return normalized in known_country_labels


def _normalize_text_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    cleaned = re.sub(r"[^a-zA-Z ]+", " ", ascii_text).casefold()
    return re.sub(r"\s{2,}", " ", cleaned).strip()


@lru_cache(maxsize=1)
def _known_country_labels() -> frozenset[str]:
    labels = {_normalize_text_label(country) for country in COUNTRY_CENTROIDS}
    labels.update(_normalize_text_label(alias) for alias in COUNTRY_ALIASES)
    labels.update(
        {
            "united kingdom",
            "uk",
            "u k",
            "united arab emirates",
            "uae",
            "south korea",
            "north macedonia",
        }
    )
    return frozenset(label for label in labels if label)


def _build_overview_shops(shops: list[CoffeeShop]) -> tuple[list[dict[str, object]], dict[str, object]]:
    payload: list[dict[str, object]] = []
    invalid_country_count = 0
    unknown_country_count = 0
    missing_city_count = 0
    flagged_shop_ids: list[str] = []

    for shop in shops:
        country_normalized, invalid_country = normalize_country(shop.country)
        if invalid_country:
            country_normalized = UNKNOWN_COUNTRY

        if invalid_country:
            invalid_country_count += 1

        if country_normalized == UNKNOWN_COUNTRY:
            unknown_country_count += 1

        city = _city_from_shop(shop, country_normalized)
        if not city:
            missing_city_count += 1

        item = {
            "id": _shop_id(shop),
            "name": _normalize_shop_text(shop.name),
            "rank": shop.rank,
            "category": normalize_category(shop.category),
            "edition_year": normalize_edition_year(shop.edition_year),
            "country_raw": _normalize_shop_text(shop.country),
            "country_normalized": country_normalized,
            "city": city,
            "address": _normalize_shop_text(shop.address),
            "source_url": _normalize_shop_text(shop.source_url),
            "google_maps_url": _google_maps_link(shop),
            "mobile_google_maps_url": _mobile_maps_link(shop),
            "rank_band": _rank_band(shop.rank),
            "formatted_address": _normalize_shop_text(shop.formatted_address),
            "place_id": _normalize_shop_text(shop.place_id),
            "lat": shop.lat,
            "lng": shop.lng,
        }
        payload.append(item)

        if invalid_country:
            flagged_shop_ids.append(str(item["id"]))

    data_quality = {
        "invalid_country_count": invalid_country_count,
        "unknown_country_count": unknown_country_count,
        "missing_city_count": missing_city_count,
        "flagged_shop_ids": flagged_shop_ids,
    }
    return payload, data_quality


def _build_overview_countries(overview_shops: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "shop_count": 0,
            "top_100_count": 0,
            "south_america_count": 0,
            "primary_shop": None,
        }
    )

    for shop in overview_shops:
        country = str(shop["country_normalized"])
        bucket = grouped[country]
        bucket["shop_count"] = int(bucket["shop_count"]) + 1
        if shop["category"] == TOP_100_CATEGORY:
            bucket["top_100_count"] = int(bucket["top_100_count"]) + 1
        if shop["category"] == SOUTH_AMERICA_CATEGORY:
            bucket["south_america_count"] = int(bucket["south_america_count"]) + 1

        current = bucket["primary_shop"]
        if current is None or int(shop["rank"]) < int(current["rank"]):
            bucket["primary_shop"] = shop

    max_count = max((int(item["shop_count"]) for item in grouped.values()), default=1)

    overview_countries: list[dict[str, object]] = []
    for country, bucket in grouped.items():
        lat, lng = country_centroid(country)
        ratio = int(bucket["shop_count"]) / max_count
        size = round(16 + ratio * 40, 2)
        overview_countries.append(
            {
                "country": country,
                "lat": lat,
                "lng": lng,
                "shop_count": int(bucket["shop_count"]),
                "top_100_count": int(bucket["top_100_count"]),
                "south_america_count": int(bucket["south_america_count"]),
                "marker_color": country_base_color(country),
                "marker_size_px": size,
                "primary_shop": bucket["primary_shop"],
            }
        )

    return sorted(overview_countries, key=lambda value: (-int(value["shop_count"]), str(value["country"])))


def _build_overview_filters(
    overview_shops: list[dict[str, object]], overview_countries: list[dict[str, object]]
) -> dict[str, object]:
    category_counts = Counter(str(shop["category"]) for shop in overview_shops)
    categories = [
        {
            "key": TOP_100_CATEGORY,
            "label": "Top 100 World",
            "count": int(category_counts.get(TOP_100_CATEGORY, 0)),
            "active": True,
        },
        {
            "key": SOUTH_AMERICA_CATEGORY,
            "label": "South America 100",
            "count": int(category_counts.get(SOUTH_AMERICA_CATEGORY, 0)),
            "active": True,
        },
    ]

    countries = [
        {
            "key": str(country["country"]),
            "label": str(country["country"]),
            "count": int(country["shop_count"]),
        }
        for country in overview_countries
    ]

    edition_counts = Counter(int(shop["edition_year"]) for shop in overview_shops)
    editions = [
        {"key": year, "label": str(year), "count": count}
        for year, count in sorted(edition_counts.items(), reverse=True)
    ]

    return {
        "categories": categories,
        "countries": countries,
        "editions": editions,
        "rank_bands": RANK_BANDS,
        "defaults": {
            "active_categories": [TOP_100_CATEGORY, SOUTH_AMERICA_CATEGORY],
            "active_editions": [edition["key"] for edition in editions],
            "country": "All",
            "rank_band": "All",
        },
    }


def _rank_band(rank: int) -> str:
    for item in RANK_BANDS:
        if int(item["min"]) <= rank <= int(item["max"]):
            return str(item["key"])
    return "Other"


def _shop_id(shop: CoffeeShop) -> str:
    edition = normalize_edition_year(shop.edition_year)
    base = f"{edition}-{normalize_category(shop.category)}-{shop.rank}-{shop.name}".casefold()
    normalized = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return normalized or f"shop-{shop.rank}"

app = create_app(
    data_file=DEFAULT_DATA_FILE,
    csv_file=DEFAULT_CSV_FILE,
    kml_file=DEFAULT_KML_FILE,
)
