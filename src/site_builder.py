from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.category_utils import SOUTH_AMERICA_CATEGORY, TOP_100_CATEGORY
from src.web_app import (
    _build_ordered_links,
    _build_overview_countries,
    _build_overview_filters,
    _build_overview_shops,
    _load_shops,
)

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"


def build_static_site(
    data_file: Path,
    site_dir: Path,
    csv_file: Path,
    kml_file: Path,
) -> None:
    site_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = site_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    shops = _load_shops(data_file)
    normalized_shops = sorted(shops, key=lambda value: (value.rank, value.category, value.name))

    category_counts = Counter(shop.category for shop in normalized_shops)
    top_100_links = _build_ordered_links(normalized_shops, TOP_100_CATEGORY)
    south_america_links = _build_ordered_links(normalized_shops, SOUTH_AMERICA_CATEGORY)

    overview_shops, data_quality = _build_overview_shops(normalized_shops)
    overview_countries = _build_overview_countries(overview_shops)
    overview_filters = _build_overview_filters(overview_shops, overview_countries)

    html_output = _template_env().get_template("index.html").render(
        shops=normalized_shops,
        total_shops=len(normalized_shops),
        category_counts=dict(sorted(category_counts.items())),
        csv_available=csv_file.exists(),
        kml_available=kml_file.exists(),
        csv_url="../output/coffee_shops.csv" if csv_file.exists() else "",
        kml_url="../output/coffee_shops.kml" if kml_file.exists() else "",
        top_100_links=top_100_links,
        south_america_links=south_america_links,
        south_links=south_america_links,
        overview_shops=overview_shops,
        overview_countries=overview_countries,
        overview_filters=overview_filters,
        data_quality=data_quality,
        google_maps_js_api_key=_google_maps_js_key(),
        data_updated=_data_updated_date(data_file),
    )

    (site_dir / "index.html").write_text(html_output, encoding="utf-8")
    (assets_dir / "style.css").write_text(
        "/* styles are inlined in templates/index.html for the static Pages build. */\n",
        encoding="utf-8",
    )


def _template_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(("html", "xml")),
    )


def _data_updated_date(data_file: Path) -> str:
    """Date of the last data refresh, from data/metadata.json ('' when absent)."""
    metadata_file = data_file.parent / "metadata.json"
    if not metadata_file.exists():
        return ""
    try:
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(metadata.get("updated_at_utc", ""))[:10]


def _google_maps_js_key() -> str:
    embed_enabled = os.getenv("EMBED_GOOGLE_MAPS_JS_KEY", "").strip().lower()
    if embed_enabled not in {"1", "true", "yes", "on"}:
        return ""
    for env_key in ("GOOGLE_MAPS_JS_API_KEY", "GOOGLE_MAPS_API_KEY"):
        env_value = os.getenv(env_key, "").strip()
        if env_value:
            return env_value
    return ""
