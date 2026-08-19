import csv
from collections import defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET

from src.category_utils import (
    SOUTH_AMERICA_CATEGORY,
    TOP_100_CATEGORY,
    normalize_category,
    normalize_edition_year,
)
from src.models import CoffeeShop

KML_NS = "http://www.opengis.net/kml/2.2"
ET.register_namespace("", KML_NS)


CSV_HEADERS = [
    "rank",
    "name",
    "city",
    "country",
    "category",
    "edition_year",
    "lat",
    "lng",
    "place_id",
    "formatted_address",
]


def _style_url(rank: int) -> str:
    return "#top10" if rank <= 10 else "#default"


def generate_kml(shops: list[CoffeeShop], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    grouped: dict[tuple[int, str], list[CoffeeShop]] = defaultdict(list)
    for shop in shops:
        key = (normalize_edition_year(shop.edition_year), normalize_category(shop.category))
        grouped[key].append(shop)

    kml = ET.Element(f"{{{KML_NS}}}kml")
    doc = ET.SubElement(kml, f"{{{KML_NS}}}Document")
    ET.SubElement(doc, f"{{{KML_NS}}}name").text = "Top 100 Best Coffee Shops"

    top10_style = ET.SubElement(doc, f"{{{KML_NS}}}Style", id="top10")
    top10_icon_style = ET.SubElement(top10_style, f"{{{KML_NS}}}IconStyle")
    ET.SubElement(top10_icon_style, f"{{{KML_NS}}}scale").text = "1.2"

    default_style = ET.SubElement(doc, f"{{{KML_NS}}}Style", id="default")
    default_icon_style = ET.SubElement(default_style, f"{{{KML_NS}}}IconStyle")
    ET.SubElement(default_icon_style, f"{{{KML_NS}}}scale").text = "1.0"

    # Newest edition first, then the canonical list order, so a My Maps import
    # shows this year's layers above the archived ones.
    ordered_categories = [TOP_100_CATEGORY, SOUTH_AMERICA_CATEGORY]
    def _folder_order(key: tuple[int, str]) -> tuple[int, bool, str]:
        year, category = key
        return (-year, category not in ordered_categories, category)

    for key in sorted(grouped.keys(), key=_folder_order):
        year, category = key
        category_shops = grouped[key]
        folder = ET.SubElement(doc, f"{{{KML_NS}}}Folder")
        ET.SubElement(folder, f"{{{KML_NS}}}name").text = f"{category} {year}"

        for shop in sorted(category_shops, key=lambda value: value.rank):
            placemark = ET.SubElement(folder, f"{{{KML_NS}}}Placemark")
            ET.SubElement(placemark, f"{{{KML_NS}}}name").text = f"{shop.rank}. {shop.name}"
            ET.SubElement(placemark, f"{{{KML_NS}}}description").text = f"{shop.city}, {shop.country}"
            ET.SubElement(placemark, f"{{{KML_NS}}}styleUrl").text = _style_url(shop.rank)
            if shop.lat is not None and shop.lng is not None:
                point = ET.SubElement(placemark, f"{{{KML_NS}}}Point")
                ET.SubElement(point, f"{{{KML_NS}}}coordinates").text = f"{shop.lng},{shop.lat},0"

    tree = ET.ElementTree(kml)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def generate_csv(shops: list[CoffeeShop], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()
        ordered = sorted(
            shops,
            key=lambda value: (
                -normalize_edition_year(value.edition_year),
                value.rank,
                normalize_category(value.category),
                value.name,
            ),
        )
        for shop in ordered:
            row = {header: shop.to_dict().get(header) for header in CSV_HEADERS}
            row["category"] = normalize_category(shop.category)
            row["edition_year"] = normalize_edition_year(shop.edition_year)
            writer.writerow(row)
