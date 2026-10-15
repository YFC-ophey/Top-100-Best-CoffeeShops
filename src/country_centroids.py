from __future__ import annotations

import re
from typing import Final

UNKNOWN_COUNTRY: Final[str] = "Unknown"

COUNTRY_ALIASES: Final[dict[str, str]] = {
    "eeuu": "USA",
    "méxico": "Mexico",
    "mexico": "Mexico",
    "united states": "USA",
    "united states of america": "USA",
    "usa": "USA",
    "uk": "United Kingdom",
    "u k": "United Kingdom",
    "united kingdom": "United Kingdom",
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "texas usa": "USA",
    "illinois usa": "USA",
}

COUNTRY_CENTROIDS: Final[dict[str, tuple[float, float]]] = {
    "Argentina": (-38.4161, -63.6167),
    "Australia": (-25.2744, 133.7751),
    "Austria": (47.5162, 14.5501),
    "Belgium": (50.5039, 4.4699),
    "Bolivia": (-16.2902, -63.5887),
    "Brazil": (-14.2350, -51.9253),
    "Bulgaria": (42.7339, 25.4858),
    "Canada": (56.1304, -106.3468),
    "Chile": (-35.6751, -71.5430),
    "China": (35.8617, 104.1954),
    "Colombia": (4.5709, -74.2973),
    "Costa Rica": (9.7489, -83.7534),
    "Czech Republic": (49.8175, 15.4730),
    "Denmark": (56.2639, 9.5018),
    "Dominican Republic": (18.7357, -70.1627),
    "Ecuador": (-1.8312, -78.1834),
    "Egypt": (26.8206, 30.8025),
    "El Salvador": (13.7942, -88.8965),
    "England": (52.3555, -1.1743),
    "Ethiopia": (9.1450, 40.4897),
    "France": (46.2276, 2.2137),
    "Greece": (39.0742, 21.8243),
    "Guatemala": (15.7835, -90.2308),
    "Honduras": (15.2000, -86.2419),
    "Ireland": (53.4129, -8.2439),
    "Italy": (41.8719, 12.5674),
    "Japan": (36.2048, 138.2529),
    "Macedonia": (41.6086, 21.7453),
    "Malaysia": (4.2105, 101.9758),
    "Mexico": (23.6345, -102.5528),
    "Netherlands": (52.1326, 5.2913),
    "Nicaragua": (12.8654, -85.2072),
    "Norway": (60.4720, 8.4689),
    "Oman": (21.4735, 55.9754),
    "Paraguay": (-23.4425, -58.4438),
    "Peru": (-9.1900, -75.0152),
    "Portugal": (39.3999, -8.2245),
    "Qatar": (25.3548, 51.1839),
    "Republic of Korea": (35.9078, 127.7669),
    "Romania": (45.9432, 24.9668),
    "Rwanda": (-1.9403, 29.8739),
    "Scotland": (56.4907, -4.2026),
    "Singapore": (1.3521, 103.8198),
    "South Africa": (-30.5595, 22.9375),
    "Spain": (40.4637, -3.7492),
    "Switzerland": (46.8182, 8.2275),
    "Taiwan": (23.6978, 120.9605),
    "Thailand": (15.8700, 100.9925),
    "The Philippines": (12.8797, 121.7740),
    "Turkey": (38.9637, 35.2433),
    "UAE": (23.4241, 53.8478),
    "United Kingdom": (55.3781, -3.4360),
    "USA": (37.0902, -95.7129),
    "Uruguay": (-32.5228, -55.7658),
    "Venezuela": (6.4238, -66.5897),
    # Regional-list additions: Google DSPL canonical countries.csv (2026-09-09).
    # https://developers.google.com/public-data/docs/canonical/countries_csv
    "Albania": (41.153332, 20.168331),
    "Armenia": (40.069099, 45.038189),
    "Azerbaijan": (40.143105, 47.576927),
    "Belarus": (53.709807, 27.953389),
    "Croatia": (45.1, 15.2),
    "Estonia": (58.595272, 25.013607),
    "Finland": (61.92411, 25.748151),
    "Georgia": (42.315407, 43.356892),
    "Germany": (51.165691, 10.451526),
    "Hungary": (47.162494, 19.503304),
    "Iceland": (64.963051, -19.020835),
    "Latvia": (56.879635, 24.603189),
    "Lithuania": (55.169438, 23.881275),
    "Luxembourg": (49.815273, 6.129583),
    "Montenegro": (42.708678, 19.37439),
    "Poland": (51.919438, 19.145136),
    "Puerto Rico": (18.220833, -66.590149),
    "Serbia": (44.016521, 21.005859),
    "Slovakia": (48.669026, 19.699024),
    "Slovenia": (46.151241, 14.995463),
    "Sweden": (60.128161, 18.643501),
    "Ukraine": (48.379433, 31.16558),
    UNKNOWN_COUNTRY: (8.0, 0.0),
}

COUNTRY_BASE_COLORS: Final[dict[str, str]] = {
    "Argentina": "#74ACDF",
    "Australia": "#00008B",
    "Austria": "#ED2939",
    "Belgium": "#FDDA24",
    "Bolivia": "#007934",
    "Brazil": "#009C3B",
    "Bulgaria": "#00966E",
    "Canada": "#FF0000",
    "Chile": "#D52B1E",
    "China": "#DE2910",
    "Colombia": "#FCD116",
    "Costa Rica": "#002B7F",
    "Czech Republic": "#D7141A",
    "Denmark": "#C60C30",
    "Dominican Republic": "#002D62",
    "Ecuador": "#FFD100",
    "Egypt": "#CE1126",
    "El Salvador": "#0F47AF",
    "England": "#CF081F",
    "Ethiopia": "#009A44",
    "France": "#002395",
    "Greece": "#004C98",
    "Guatemala": "#4997D0",
    "Honduras": "#0073CF",
    "Ireland": "#169B62",
    "Italy": "#008C45",
    "Japan": "#BC002D",
    "Macedonia": "#D20000",
    "Malaysia": "#010066",
    "Mexico": "#006847",
    "Netherlands": "#AE1C28",
    "Nicaragua": "#0067C6",
    "Norway": "#EF2B2D",
    "Oman": "#DB161B",
    "Paraguay": "#D52B1E",
    "Peru": "#D91023",
    "Portugal": "#006600",
    "Qatar": "#8D1B3D",
    "Republic of Korea": "#CD2E3A",
    "Romania": "#002B7F",
    "Rwanda": "#20603D",
    "Scotland": "#005EB8",
    "Singapore": "#EF3340",
    "South Africa": "#007749",
    "Spain": "#AA151B",
    "Switzerland": "#D52B1E",
    "Taiwan": "#000095",
    "Thailand": "#A51931",
    "The Philippines": "#0038A8",
    "Turkey": "#E30A17",
    "UAE": "#00732F",
    "United Kingdom": "#1F3C88",
    "USA": "#3C3B6E",
    "Uruguay": "#001489",
    "Venezuela": "#FFCC00",
}


def normalize_country(value: str | None) -> tuple[str, bool]:
    if value is None:
        return UNKNOWN_COUNTRY, True

    cleaned = value.strip()
    if not cleaned:
        return UNKNOWN_COUNTRY, True

    alias_key = _alias_key(cleaned)
    if alias_key in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[alias_key], False

    parenthetical = re.fullmatch(r"(.+?)\s*\(([^)]+)\)\s*", cleaned)
    if parenthetical:
        inner_value = parenthetical.group(2)
        inner_key = _alias_key(inner_value)
        if inner_key in COUNTRY_ALIASES:
            return COUNTRY_ALIASES[inner_key], False

    if any(char.isdigit() for char in cleaned):
        return UNKNOWN_COUNTRY, True

    return cleaned, False


def _alias_key(value: str) -> str:
    return re.sub(r"\s{2,}", " ", value.casefold().replace(".", " ").replace(",", " ")).strip()


def country_centroid(country: str) -> tuple[float, float]:
    return COUNTRY_CENTROIDS.get(country, COUNTRY_CENTROIDS[UNKNOWN_COUNTRY])


def country_base_color(country: str) -> str:
    return COUNTRY_BASE_COLORS.get(country, "#888899")
