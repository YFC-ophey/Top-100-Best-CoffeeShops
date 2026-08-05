import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from src.models import CoffeeShop
from src.web_app import _best_map_query_text, _city_from_address, _google_maps_link, _mobile_maps_link, create_app


def _write_state(path: Path) -> None:
    payload = [
        {
            "name": "Coffee Collective",
            "city": "Copenhagen",
            "country": "Denmark",
            "rank": 1,
            "category": "Top 100",
            "lat": None,
            "lng": None,
            "place_id": "abc123",
            "formatted_address": "Copenhagen, Denmark",
        },
        {
            "name": "Proud Mary",
            "city": "Melbourne",
            "country": "Australia",
            "rank": 2,
            "category": "South",
            "lat": None,
            "lng": None,
            "place_id": "def456",
            "formatted_address": "Melbourne, Australia",
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_home_page_renders_roast_overview_with_south_america_label(tmp_path: Path) -> None:
    data_file = tmp_path / "data" / "current_list.json"
    csv_file = tmp_path / "output" / "coffee_shops.csv"
    kml_file = tmp_path / "output" / "coffee_shops.kml"
    _write_state(data_file)
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    csv_file.write_text("rank,name\n1,Coffee Collective\n", encoding="utf-8")
    kml_file.write_text("<kml></kml>", encoding="utf-8")

    app = create_app(data_file=data_file, csv_file=csv_file, kml_file=kml_file)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "ROAST." in response.text
    assert "World's 100 Best Coffee Shops" in response.text
    assert "Interactive map with country-level shop density and source-backed shop details." in response.text
    assert "flex: 0 0 clamp(310px, 27vw, 370px);" in response.text
    assert 'id="filters-panel" class="filters-panel"' in response.text
    assert 'class="sidebar-left glass-panel"' not in response.text
    assert response.text.index('id="filters-panel"') < response.text.index("<p>Coffee Shop Preview</p>")
    assert 'class="banner-subtitle"' in response.text
    assert 'id="overview-map"' in response.text
    assert "South America" in response.text
    assert "Top 100 World" in response.text
    assert "South America 100" in response.text
    assert "Top 100 World (" not in response.text
    assert "South America 100 (" not in response.text
    assert "Top 20" in response.text
    assert "Top 50" in response.text
    assert "The Rest" in response.text
    assert "Source: <a href=\"https://theworlds100bestcoffeeshops.com/\"" in response.text
    assert "Data Quality" not in response.text
    assert "Total shops" not in response.text
    assert ">CSV<" not in response.text
    assert ">KML<" not in response.text
    assert "<th>City</th>" in response.text
    assert "<th>Address</th>" in response.text
    assert ">Map</a>" not in response.text
    assert ">Filter<" in response.text
    assert ">Filters<" not in response.text
    assert "max-width: none;" in response.text
    assert "color: #f1d0b1;" in response.text
    assert "color: var(--brand-gold);" in response.text
    assert '<div class="map-hint glass-panel hidden"></div>' in response.text
    assert "Warm espresso map mode: zoom out for country bubbles, zoom in for individual shops." not in response.text
    assert "Single-shop countries are hidden at global zoom." not in response.text
    assert 'const GLOBAL_COUNTRY_MIN_SHOPS = 2;' in response.text
    assert "path: google.maps.SymbolPath.CIRCLE" in response.text
    assert 'labelOrigin: new google.maps.Point(0, 0)' in response.text
    assert 'const SHOP_PIN_PATH = "M 0,-19 C -5.8,-19 -10.8,-14.5 -10.8,-8.8 C -10.8,-1.9 0,5.8 0,5.8 C 0,5.8 10.8,-1.9 10.8,-8.8 C 10.8,-14.5 5.8,-19 0,-19 Z M 0,-12.5 C -2.3,-12.5 -4.2,-10.6 -4.2,-8.3 C -4.2,-6 -2.3,-4.1 0,-4.1 C 2.3,-4.1 4.2,-6 4.2,-8.3 C 4.2,-10.6 2.3,-12.5 0,-12.5 Z";' in response.text
    assert 'gestureHandling: "greedy"' in response.text
    assert "zoomControl: true" in response.text
    assert "#a5755b" in response.text
    assert "position: static;" in response.text
    assert "justify-content: space-between;" in response.text
    assert '<div id="overview-map-meta-row" class="map-meta-row">' in response.text
    assert "text-align: right;" in response.text
    assert 'id="overview-map-meta-row"' in response.text
    assert 'document.getElementById("overview-map-meta-row").classList.toggle("is-hidden", mode !== "map");' in response.text
    assert 'id="overview-list-source"' in response.text
    assert "font-size: 0.58rem;" in response.text
    assert "function shopTooltipText(shop)" in response.text
    assert 'id="map-click-dialog"' in response.text
    assert 'url("/map-style-inspo.png") center / cover no-repeat' not in response.text
    assert '{ featureType: "poi", stylers: [{ visibility: "off" }] }' in response.text
    assert "shop.lat !== null" in response.text
    assert "shop.lng !== null" in response.text
    assert "Only source-backed fields from the scraped dataset are shown in this panel." not in response.text
    assert "Coffee Shop Preview" in response.text
    assert "new google.maps.InfoWindow()" not in response.text
    assert "grid-template-columns: 1fr 1fr;" in response.text
    assert "countriesSorted = [...overviewFilters.countries].sort" in response.text
    assert "focusCountry: null" in response.text
    assert "World's Best Coffee Shops Complete Map" in response.text
    assert "https://buymeacoffee.com/opheliachen" in response.text


def test_health_endpoint_reports_ok(tmp_path: Path) -> None:
    app = create_app(
        data_file=tmp_path / "data" / "current_list.json",
        csv_file=tmp_path / "output" / "coffee_shops.csv",
        kml_file=tmp_path / "output" / "coffee_shops.kml",
    )
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_artifact_endpoint_serves_csv(tmp_path: Path) -> None:
    data_file = tmp_path / "data" / "current_list.json"
    csv_file = tmp_path / "output" / "coffee_shops.csv"
    kml_file = tmp_path / "output" / "coffee_shops.kml"
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    csv_file.write_text("rank,name\n1,Coffee Collective\n", encoding="utf-8")

    app = create_app(data_file=data_file, csv_file=csv_file, kml_file=kml_file)
    client = TestClient(app)

    response = client.get("/artifacts/csv")

    assert response.status_code == 200
    assert "Coffee Collective" in response.text


def test_map_style_inspo_endpoint_serves_png(tmp_path: Path) -> None:
    app = create_app(
        data_file=tmp_path / "data" / "current_list.json",
        csv_file=tmp_path / "output" / "coffee_shops.csv",
        kml_file=tmp_path / "output" / "coffee_shops.kml",
    )
    client = TestClient(app)

    response = client.get("/map-style-inspo.png")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")


def test_home_page_renders_map_links_and_legacy_south_normalization(tmp_path: Path) -> None:
    data_file = tmp_path / "data" / "current_list.json"
    payload = [
        {
            "name": "Shop B",
            "city": "",
            "country": "USA",
            "rank": 2,
            "category": "Top 100",
            "formatted_address": "Bleecker St, New York, NY 10014, USA",
        },
        {
            "name": "Shop A",
            "city": "",
            "country": "USA",
            "rank": 1,
            "category": "Top 100",
            "place_id": "pid1",
            "formatted_address": "R. dos Sapateiros 111, 1100-619 Lisbon, Portugal",
        },
        {
            "name": "Shop S",
            "city": "",
            "country": "Australia",
            "rank": 1,
            "category": "South",
            "place_id": None,
        },
    ]
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps(payload), encoding="utf-8")

    app = create_app(
        data_file=data_file,
        csv_file=tmp_path / "output" / "coffee_shops.csv",
        kml_file=tmp_path / "output" / "coffee_shops.kml",
    )
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Top 100 Links" not in response.text
    assert "South America Links" not in response.text
    assert "Shop+A%2C+USA" not in response.text
    assert "R. dos Sapateiros 111, 1100-619 Lisbon, Portugal" in response.text
    assert "maps/place/?q=place_id%3Apid1" in response.text
    assert "Shop+S%2C+Australia" in response.text
    assert response.text.index("Shop A") < response.text.index("Shop B")
    assert "South America" in response.text
    assert "<th>Address</th>" in response.text
    assert ">Map</a>" not in response.text
    assert "shopPosition(" not in response.text
    assert "hashString(" not in response.text


def test_mobile_maps_link_prefers_coordinates_and_fallback_query() -> None:
    with_coordinates = CoffeeShop(
        name="Apartment Coffee",
        city="Singapore",
        country="Singapore",
        rank=11,
        category="Top 100",
        lat=1.2955,
        lng=103.8520,
        formatted_address="A fallback address",
        place_id="place-id-ignored-on-mobile",
    )
    coords_link = _mobile_maps_link(with_coordinates)
    coords_query = parse_qs(urlparse(coords_link).query)
    assert coords_query["destination"] == ["Apartment Coffee, A fallback address"]

    fallback_shop = CoffeeShop(
        name="Onyx Coffee LAB",
        city="Rogers, Arkansas",
        country="USA",
        rank=1,
        category="Top 100",
        formatted_address=None,
        place_id="place-id-ignored-on-mobile",
        lat=None,
        lng=None,
    )
    fallback_link = _mobile_maps_link(fallback_shop)
    fallback_query = parse_qs(urlparse(fallback_link).query)
    assert fallback_query["destination"] == ["Onyx Coffee LAB, Rogers, Arkansas, USA"]


def test_home_page_includes_mobile_map_urls_in_overview_payload(tmp_path: Path) -> None:
    data_file = tmp_path / "data" / "current_list.json"
    payload = [
        {
            "name": "The Folks",
            "city": "Lisbon",
            "country": "Portugal",
            "rank": 88,
            "category": "Top 100",
            "place_id": "pid1",
            "lat": 38.711,
            "lng": -9.138,
            "formatted_address": "R. dos Sapateiros 111, 1100-051 Lisboa, Portugal",
        }
    ]
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps(payload), encoding="utf-8")

    app = create_app(
        data_file=data_file,
        csv_file=tmp_path / "output" / "coffee_shops.csv",
        kml_file=tmp_path / "output" / "coffee_shops.kml",
    )
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert '"google_maps_url": "https://www.google.com/maps/place/?q=place_id%3Apid1"' in response.text
    assert (
        '"mobile_google_maps_url": '
        '"https://www.google.com/maps/dir/?api=1\\u0026destination=The+Folks%2C+R.+dos+Sapateiros+111%2C+1100-051+Lisboa%2C+Portugal"'
        in response.text
    )


def test_overview_table_uses_address_column_per_row(tmp_path: Path) -> None:
    data_file = tmp_path / "data" / "current_list.json"
    payload = [
        {
            "name": "Shop A",
            "city": "Lisbon",
            "country": "Portugal",
            "rank": 1,
            "category": "Top 100",
            "place_id": "pid1",
            "formatted_address": "R. dos Sapateiros 111, 1100-619 Lisbon, Portugal",
        },
        {
            "name": "Shop B",
            "city": "Miraflores",
            "country": "Peru",
            "rank": 2,
            "category": "South America",
            "place_id": None,
            "formatted_address": "Entre Pardos Chicken y Wong, Mal. de la Reserva 610, Miraflores 15074, Peru",
        },
    ]
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps(payload), encoding="utf-8")

    app = create_app(
        data_file=data_file,
        csv_file=tmp_path / "output" / "coffee_shops.csv",
        kml_file=tmp_path / "output" / "coffee_shops.kml",
    )
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    html = response.text

    match_a = re.search(
        r"<tr>\s*<td>1</td>\s*<td>Shop A</td>\s*<td>Lisbon</td>\s*<td>Portugal</td>\s*<td>Top 100</td>\s*<td>2026</td>\s*<td>R\. dos Sapateiros 111, 1100-619 Lisbon, Portugal</td>\s*</tr>",
        html,
        flags=re.DOTALL,
    )
    assert match_a, "Shop A row should include its address in the Address column."

    match_b = re.search(
        r"<tr>\s*<td>2</td>\s*<td>Shop B</td>\s*<td>Miraflores</td>\s*<td>Peru</td>\s*<td>South America</td>\s*<td>2026</td>\s*<td>Entre Pardos Chicken y Wong, Mal\. de la Reserva 610, Miraflores 15074, Peru</td>\s*</tr>",
        html,
        flags=re.DOTALL,
    )
    assert match_b, "Shop B row should include its address in the Address column."

    assert "<th>Address</th>" in html
    assert ">Map</a>" not in html


def test_overview_payload_uses_country_markers_without_shop_coordinates(tmp_path: Path) -> None:
    data_file = tmp_path / "data" / "current_list.json"
    payload = [
        {
            "name": "Metric",
            "city": "",
            "country": "EEUU",
            "rank": 95,
            "category": "Top 100",
            "place_id": None,
            "lat": None,
            "lng": None,
            "formatted_address": None,
        },
        {
            "name": "El Terrible Juan Café",
            "city": "",
            "country": "México",
            "rank": 96,
            "category": "Top 100",
            "place_id": None,
            "lat": None,
            "lng": None,
            "formatted_address": None,
        },
        {
            "name": "Azura",
            "city": "",
            "country": "69",
            "rank": 68,
            "category": "Top 100",
            "place_id": None,
            "lat": None,
            "lng": None,
            "formatted_address": None,
        },
        {
            "name": "Malformed Country Shop",
            "city": "",
            "country": "1234",
            "rank": 67,
            "category": "Top 100",
            "place_id": None,
            "lat": None,
            "lng": None,
            "formatted_address": None,
        },
    ]
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps(payload), encoding="utf-8")

    app = create_app(
        data_file=data_file,
        csv_file=tmp_path / "output" / "coffee_shops.csv",
        kml_file=tmp_path / "output" / "coffee_shops.kml",
    )
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert '"country_normalized": "USA"' in response.text
    assert '"country_normalized": "Mexico"' in response.text
    assert '"country_normalized": "Oman"' in response.text
    assert '"country_normalized": "Unknown"' in response.text


def test_google_maps_link_uses_required_precedence_rules() -> None:
    with_place_id = CoffeeShop(
        name="The Folks",
        city="Lisbon",
        country="Portugal",
        rank=88,
        category="Top 100",
        place_id="abc123",
        formatted_address="R. dos Sapateiros 111, 1100-619 Lisbon, Portugal",
    )
    with_address_only = CoffeeShop(
        name="Puku Puku",
        city="Miraflores",
        country="Peru",
        rank=69,
        category="South America",
        address="Entre Pardos Chicken y Wong, Mal. de la Reserva 610, Miraflores 15074, Peru",
        source_url="https://example.com",
        formatted_address=None,
    )

    with_name_city_country = CoffeeShop(
        name="Onyx Coffee LAB",
        city="Rogers, Arkansas",
        country="USA",
        rank=1,
        category="Top 100",
        formatted_address=None,
    )
    with_name_country = CoffeeShop(
        name="Shop No City",
        city="",
        country="Japan",
        rank=50,
        category="Top 100",
        formatted_address=None,
    )
    with_coordinates = CoffeeShop(
        name="Apartment Coffee",
        city="Singapore",
        country="Singapore",
        rank=11,
        category="Top 100",
        lat=1.2955,
        lng=103.8520,
        formatted_address=None,
        place_id=None,
    )

    place_link = _google_maps_link(with_place_id)
    place_query = parse_qs(urlparse(place_link).query)
    assert place_query["q"] == ["place_id:abc123"]

    address_link = _google_maps_link(with_address_only)
    address_query = parse_qs(urlparse(address_link).query)
    assert address_query["query"] == [
        "Entre Pardos Chicken y Wong, Mal. de la Reserva 610, Miraflores 15074, Peru"
    ]
    assert "query_place_id" not in address_query

    city_link = _google_maps_link(with_name_city_country)
    city_query = parse_qs(urlparse(city_link).query)
    assert city_query["query"] == ["Onyx Coffee LAB, Rogers, Arkansas, USA"]

    country_link = _google_maps_link(with_name_country)
    country_query = parse_qs(urlparse(country_link).query)
    assert country_query["query"] == ["Shop No City, Japan"]

    coords_link = _google_maps_link(with_coordinates)
    coords_query = parse_qs(urlparse(coords_link).query)
    assert coords_query["query"] == ["1.2955,103.852"]


def test_best_map_query_text_sanitizes_entities_and_duplicate_country_suffix() -> None:
    noisy = CoffeeShop(
        name="Azura &#8211; The Coffee Company",
        city="Muscat",
        country="Oman",
        rank=68,
        category="Top 100",
        formatted_address="Way Number: 9203 Building Number: 790, Muscat, Oman, Oman, Unknown",
    )
    query = _best_map_query_text(noisy)
    assert "&#8211;" not in query
    assert "Unknown" not in query
    assert "Oman, Oman" not in query
    assert "Muscat, Oman" in query

    duplicate_tokens = CoffeeShop(
        name="Repeat City Cafe",
        city="",
        country="Peru",
        rank=2,
        category="Top 100",
        formatted_address="Miraflores, Peru, Miraflores, Peru",
    )
    deduped_query = _best_map_query_text(duplicate_tokens)
    assert deduped_query == "Miraflores, Peru"


def test_rank_68_top_100_is_corrected_to_azure_muscat_oman(tmp_path: Path) -> None:
    data_file = tmp_path / "data" / "current_list.json"
    payload = [
        {
            "name": "Azura &#8211; The Coffee Company",
            "city": "",
            "country": "69",
            "rank": 68,
            "category": "Top 100",
            "formatted_address": "Way Number: 9203 Building Number: 790, Muscat, Oman",
        }
    ]
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps(payload), encoding="utf-8")

    app = create_app(
        data_file=data_file,
        csv_file=tmp_path / "output" / "coffee_shops.csv",
        kml_file=tmp_path / "output" / "coffee_shops.kml",
    )
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "Azure The Coffee Company" in response.text
    assert '"country_normalized": "Oman"' in response.text
    assert '"city": "Muscat"' in response.text
    assert "Multiple locations, Muscat, Oman" in response.text


def test_city_extraction_derives_city_from_address_patterns() -> None:
    assert _city_from_address("R. dos Sapateiros 111, 1100-619 Lisbon, Portugal", "Portugal") == "Lisbon"
    assert _city_from_address("101 E Walnut Ave Rogers, AR 72756, USA", "USA") == "Rogers"
    assert _city_from_address("Shop 2/118 Willoughby Rd, Crows Nest NSW 2065, Australia", "Australia") == "Crows Nest"
    assert _city_from_address("Calle, Calle Pte. Bolognesi 216, Arequipa, Perú", "Peru") == "Arequipa"
    assert _city_from_address("73 Berkeley St., Glasgow G3 7DX, United Kingdom", "United Kingdom") == "Glasgow"
    assert _city_from_address("Bayfield Rd, Portree IV51 9EL, United Kingdom", "United Kingdom") == "Portree"
    assert _city_from_address("205B Emmet Rd, Inchicore, Dublin 8, D08 EN29, Ireland", "Ireland") == "Dublin"
    assert (
        _city_from_address("403, Taiwan, Taichung City, West District, Fulong St, 7號1樓", "Taiwan")
        == "Taichung City"
    )
    assert (
        _city_from_address("Conesa 3705, C1429 C1429ALQ, Cdad. Autónoma de Buenos Aires, Argentina", "Argentina")
        == "Buenos Aires"
    )
    assert (
        _city_from_address("Carlos Bories 385, 6160000 Natales, Magallanes y la Antártica Chilena, Chile", "Chile")
        == "Natales"
    )


def test_home_page_uses_address_city_when_explicit_city_is_noisy(tmp_path: Path) -> None:
    data_file = tmp_path / "data" / "current_list.json"
    payload = [
        {
            "name": "Kafi Wasi Café Tostaduría",
            "city": "a white sillar (ashlar [volcanic stone]) district",
            "country": "Peru",
            "rank": 17,
            "category": "South America",
            "formatted_address": "Calle Pte. Bolognesi 216, Arequipa 04001, Peru",
        }
    ]
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps(payload), encoding="utf-8")

    app = create_app(
        data_file=data_file,
        csv_file=tmp_path / "output" / "coffee_shops.csv",
        kml_file=tmp_path / "output" / "coffee_shops.kml",
    )
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert '"city": "Arequipa"' in response.text
    assert "a white sillar (ashlar [volcanic stone]) district" not in response.text
