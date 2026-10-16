import json
from pathlib import Path

from src.site_builder import build_static_site


def test_build_static_site_generates_index_and_styles(tmp_path: Path) -> None:
    data_file = tmp_path / "data" / "current_list.json"
    output_csv = tmp_path / "output" / "coffee_shops.csv"
    output_kml = tmp_path / "output" / "coffee_shops.kml"
    site_dir = tmp_path / "site"
    payload = [
        {"name": "A", "city": "Copenhagen", "country": "Denmark", "rank": 1, "category": "Top 100"},
        {"name": "B", "city": "Lima", "country": "Peru", "rank": 1, "category": "South"},
    ]
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps(payload), encoding="utf-8")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_csv.write_text("rank,name\n1,A\n", encoding="utf-8")
    output_kml.write_text("<kml></kml>", encoding="utf-8")

    build_static_site(data_file=data_file, site_dir=site_dir, csv_file=output_csv, kml_file=output_kml)

    index = (site_dir / "index.html").read_text(encoding="utf-8")
    likes = (site_dir / "likes.html").read_text(encoding="utf-8")
    style = (site_dir / "assets" / "style.css").read_text(encoding="utf-8")
    assert "<title>ROAST. | Global Coffee Explorer</title>" in index
    assert "World's 100 Best Coffee Shops" in index
    assert "Interactive map with country-level shop density and source-backed shop details." in index
    assert 'id="overview-map"' in index
    assert ">Filter<" in index
    assert "Coffee Shop Preview" in index
    assert "<th>Address</th>" in index
    assert "Top 100 World" in index
    assert "South America 100" in index
    assert "Main Top 100" not in index
    assert "Download CSV" not in index
    assert "Open in Google Maps" not in index
    assert "World's Best Coffee Shops Complete Map" in index
    assert 'const googleMapsKey = "";' in index
    assert "const overviewShops = " in index
    assert "const overviewCountries = " in index
    assert "const overviewFilters = " in index
    assert 'href="likes.html"' in index
    assert "rate-map-button" in index
    assert 'const likesApiBase = "";' in index
    assert "Latest love notes" in likes
    assert "styles are inlined in templates/index.html" in style


def test_build_static_site_includes_mobile_directions_and_phone_table_rules(tmp_path: Path) -> None:
    data_file = tmp_path / "data" / "current_list.json"
    output_csv = tmp_path / "output" / "coffee_shops.csv"
    output_kml = tmp_path / "output" / "coffee_shops.kml"
    site_dir = tmp_path / "site"
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
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_csv.write_text("rank,name\n88,The Folks\n", encoding="utf-8")
    output_kml.write_text("<kml></kml>", encoding="utf-8")

    build_static_site(data_file=data_file, site_dir=site_dir, csv_file=output_csv, kml_file=output_kml)

    index = (site_dir / "index.html").read_text(encoding="utf-8")
    assert (
        '"mobile_google_maps_url": '
        '"https://www.google.com/maps/dir/?api=1\\u0026destination=The+Folks%2C+R.+dos+Sapateiros+111%2C+1100-051+Lisboa%2C+Portugal"'
        in index
    )
    assert "const mobileHref = String(shop.mobile_google_maps_url || \"\").trim();" in index
    assert "window.open(mobileHref, \"_blank\", \"noopener\");" in index
    assert "overflow-x: auto;" in index
    assert "white-space: normal;" in index
    assert "text-overflow: clip;" in index


def test_build_static_site_does_not_embed_env_api_key(tmp_path: Path, monkeypatch) -> None:
    data_file = tmp_path / "data" / "current_list.json"
    output_csv = tmp_path / "output" / "coffee_shops.csv"
    output_kml = tmp_path / "output" / "coffee_shops.kml"
    site_dir = tmp_path / "site"
    payload = [{"name": "A", "city": "Copenhagen", "country": "Denmark", "rank": 1, "category": "Top 100"}]
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps(payload), encoding="utf-8")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_csv.write_text("rank,name\n1,A\n", encoding="utf-8")
    output_kml.write_text("<kml></kml>", encoding="utf-8")

    monkeypatch.setenv("GOOGLE_MAPS_JS_API_KEY", "TEST_MAPS_KEY_PLACEHOLDER_DO_NOT_USE")

    build_static_site(data_file=data_file, site_dir=site_dir, csv_file=output_csv, kml_file=output_kml)

    index = (site_dir / "index.html").read_text(encoding="utf-8")
    assert "TEST_MAPS_KEY_PLACEHOLDER_DO_NOT_USE" not in index
    assert 'const googleMapsKey = "";' in index


def test_build_static_site_embeds_api_key_when_opt_in_enabled(tmp_path: Path, monkeypatch) -> None:
    data_file = tmp_path / "data" / "current_list.json"
    output_csv = tmp_path / "output" / "coffee_shops.csv"
    output_kml = tmp_path / "output" / "coffee_shops.kml"
    site_dir = tmp_path / "site"
    payload = [{"name": "A", "city": "Copenhagen", "country": "Denmark", "rank": 1, "category": "Top 100"}]
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps(payload), encoding="utf-8")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_csv.write_text("rank,name\n1,A\n", encoding="utf-8")
    output_kml.write_text("<kml></kml>", encoding="utf-8")

    monkeypatch.setenv("EMBED_GOOGLE_MAPS_JS_KEY", "1")
    monkeypatch.setenv("GOOGLE_MAPS_JS_API_KEY", "TEST_MAPS_KEY_PLACEHOLDER_DO_NOT_USE")

    build_static_site(data_file=data_file, site_dir=site_dir, csv_file=output_csv, kml_file=output_kml)

    index = (site_dir / "index.html").read_text(encoding="utf-8")
    assert 'const googleMapsKey = "TEST_MAPS_KEY_PLACEHOLDER_DO_NOT_USE";' in index


def test_build_static_site_embeds_public_likes_api_url(tmp_path: Path, monkeypatch) -> None:
    data_file = tmp_path / "data" / "current_list.json"
    output_csv = tmp_path / "output" / "coffee_shops.csv"
    output_kml = tmp_path / "output" / "coffee_shops.kml"
    site_dir = tmp_path / "site"
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps([]), encoding="utf-8")
    monkeypatch.setenv("LIKES_API_URL", "https://likes.example.test/")

    build_static_site(data_file=data_file, site_dir=site_dir, csv_file=output_csv, kml_file=output_kml)

    index = (site_dir / "index.html").read_text(encoding="utf-8")
    likes = (site_dir / "likes.html").read_text(encoding="utf-8")
    assert 'const likesApiBase = "https://likes.example.test";' in index
    assert 'const likesApiBase = "https://likes.example.test";' in likes
