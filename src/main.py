from argparse import ArgumentParser
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.generator import generate_csv, generate_kml
from src.env_utils import load_env_file
from src.geocoder import GooglePlacesGeocoder
from src.models import CoffeeShop
from src.scraper import SOURCE_URLS, enrich_shops_with_details, fetch_html, parse_coffee_shops
from src.site_builder import build_static_site
from src.state import has_shop_changes, load_previous_state

BASE_DIR = Path(__file__).resolve().parent.parent
load_env_file(BASE_DIR)
DATA_FILE = BASE_DIR / "data" / "current_list.json"
METADATA_FILE = BASE_DIR / "data" / "metadata.json"
KML_FILE = BASE_DIR / "output" / "coffee_shops.kml"
CSV_FILE = BASE_DIR / "output" / "coffee_shops.csv"
SITE_DIR = BASE_DIR / "site"

# A healthy scrape yields ~100 shops per list. If a category shrinks past this
# fraction of the previous run, assume a source redesign or partial fetch and
# abort before overwriting good committed data. Override: SCRAPE_ALLOW_SHRINK=1.
SHRINK_FLOOR_RATIO = 0.8


def _guard_against_scrape_collapse(
    previous: list[CoffeeShop], current: list[CoffeeShop]
) -> None:
    if os.getenv("SCRAPE_ALLOW_SHRINK", "").strip().lower() in {"1", "true", "yes", "on"}:
        return
    prev_counts: dict[str, int] = {}
    for shop in previous:
        prev_counts[shop.category] = prev_counts.get(shop.category, 0) + 1
    cur_counts: dict[str, int] = {}
    for shop in current:
        cur_counts[shop.category] = cur_counts.get(shop.category, 0) + 1
    for category, prev_count in prev_counts.items():
        cur_count = cur_counts.get(category, 0)
        if prev_count > 0 and cur_count < int(prev_count * SHRINK_FLOOR_RATIO):
            raise RuntimeError(
                f"Scrape collapse for '{category}': {prev_count} -> {cur_count} shops "
                f"(floor {SHRINK_FLOOR_RATIO:.0%}). The source layout likely changed; "
                "keeping the previous data. Re-run with SCRAPE_ALLOW_SHRINK=1 to force."
            )


def scrape_only(sleep_seconds: float = 1.0) -> tuple[list[CoffeeShop], bool]:
    previous = load_previous_state(DATA_FILE)
    all_shops: list[CoffeeShop] = []
    for category, url in SOURCE_URLS.items():
        html = fetch_html(url)
        all_shops.extend(parse_coffee_shops(html, category=category))

    _guard_against_scrape_collapse(previous, all_shops)
    all_shops = enrich_shops_with_details(all_shops, sleep_seconds=sleep_seconds)
    all_shops = _carry_forward_geocode(previous, all_shops)
    changed = has_shop_changes(previous, all_shops)
    _save_state(all_shops)
    generate_csv(all_shops, CSV_FILE)
    generate_kml(all_shops, KML_FILE)
    return all_shops, changed


def owner_geocode(api_key: str) -> None:
    shops = load_previous_state(DATA_FILE)
    geocoder = GooglePlacesGeocoder(api_key)
    for shop in shops:
        result = geocoder.geocode_shop(shop)
        if result:
            shop.lat = result.lat
            shop.lng = result.lng
            shop.place_id = result.place_id
            shop.formatted_address = result.formatted_address
    _save_state(shops)
    generate_csv(shops, CSV_FILE)
    generate_kml(shops, KML_FILE)


def build_site() -> None:
    build_static_site(DATA_FILE, SITE_DIR, CSV_FILE, KML_FILE)


def _save_state(shops: list[CoffeeShop]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps([shop.to_dict() for shop in shops], indent=2, ensure_ascii=False), encoding="utf-8")
    _save_metadata(shops)


def _save_metadata(shops: list[CoffeeShop]) -> None:
    """Dataset provenance for consumers of the JSON/CSV/KML and the site footer."""
    counts: dict[str, int] = {}
    for shop in shops:
        counts[shop.category] = counts.get(shop.category, 0) + 1
    metadata = {
        "updated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_shops": len(shops),
        "counts_by_category": dict(sorted(counts.items())),
        "sources": SOURCE_URLS,
        "geocoded_shops": sum(1 for s in shops if s.lat is not None and s.lng is not None),
    }
    METADATA_FILE.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _carry_forward_geocode(previous: list[CoffeeShop], current: list[CoffeeShop]) -> list[CoffeeShop]:
    previous_by_source: dict[str, CoffeeShop] = {}
    previous_by_identity: dict[tuple[str, int, str, str], CoffeeShop] = {}

    for shop in previous:
        if shop.source_url:
            previous_by_source[shop.source_url.strip().casefold()] = shop
        previous_by_identity[(shop.category.strip().casefold(), shop.rank, shop.name.strip().casefold(), shop.country.strip().casefold())] = shop

    for shop in current:
        match: CoffeeShop | None = None
        if shop.source_url:
            match = previous_by_source.get(shop.source_url.strip().casefold())
        if match is None:
            identity = (shop.category.strip().casefold(), shop.rank, shop.name.strip().casefold(), shop.country.strip().casefold())
            match = previous_by_identity.get(identity)
        if match is None:
            continue

        if shop.place_id is None and match.place_id:
            shop.place_id = match.place_id
        if shop.lat is None and match.lat is not None:
            shop.lat = match.lat
        if shop.lng is None and match.lng is not None:
            shop.lng = match.lng
        if shop.formatted_address is None and match.formatted_address:
            shop.formatted_address = match.formatted_address

    return current


def main() -> int:
    parser = ArgumentParser(description="Top 100 coffee shops utility CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    scrape = sub.add_parser("scrape-only", help="Scrape and enrich source data without requiring API keys")
    scrape.add_argument(
        "--sleep-seconds",
        type=float,
        default=1.0,
        help="Delay between detail-page requests (default: 1.0)",
    )
    sub.add_parser("build-site", help="Build static site from current_list.json")
    geocode = sub.add_parser("owner-geocode", help="Optional owner-only geocoding refresh")
    geocode.add_argument("--api-key", required=True, help="Owner Google Places API key")
    args = parser.parse_args()

    if args.command == "scrape-only":
        shops, changed = scrape_only(sleep_seconds=args.sleep_seconds)
        print(f"Scraped {len(shops)} shops. Detected changes: {changed}")
        return 0
    if args.command == "build-site":
        build_site()
        print("Site built at site/index.html")
        return 0
    if args.command == "owner-geocode":
        owner_geocode(args.api_key)
        print("Owner geocode refresh complete.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
