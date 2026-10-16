import json
from pathlib import Path

from src.scraper import enrich_shops_with_details, parse_coffee_shops
from src.site_builder import build_static_site


def test_ranking_card_images_follow_their_own_shop_links() -> None:
    html = """
    <img src="https://theworlds100bestcoffeeshops.com/wp-content/uploads/logo.png">
    <div data-elementor-type="loop-item">
      <a href="https://theworlds100bestcoffeeshops.com/locales/first/">
        <img src="https://theworlds100bestcoffeeshops.com/wp-content/uploads/first.jpg">
      </a>
      <p class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/first/">1</a></p>
      <h1 class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/first/">First</a></h1>
      <p class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/first/">Colombia</a></p>
    </div>
    <div data-elementor-type="loop-item">
      <a href="https://theworlds100bestcoffeeshops.com/locales/second/">
        <img src="https://theworlds100bestcoffeeshops.com/wp-content/uploads/second.webp">
      </a>
      <p class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/second/">2</a></p>
      <h1 class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/second/">Second</a></h1>
      <p class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/second/">Peru</a></p>
    </div>
    """

    shops = parse_coffee_shops(html, "South America")

    assert [shop.image_url for shop in shops] == [
        "https://theworlds100bestcoffeeshops.com/wp-content/uploads/first.jpg",
        "https://theworlds100bestcoffeeshops.com/wp-content/uploads/second.webp",
    ]


def test_detail_open_graph_image_fills_missing_list_image() -> None:
    shop = parse_coffee_shops(
        '<p class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/first/">1</a></p>'
        '<h1 class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/first/">First</a></h1>'
        '<p class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/first/">Colombia</a></p>',
        "South America",
    )[0]
    details = '<meta content="https://theworlds100bestcoffeeshops.com/wp-content/uploads/first.jpg" property="og:image">'

    enriched = enrich_shops_with_details([shop], fetcher=lambda _: details, sleep_seconds=0)

    assert enriched[0].image_url == "https://theworlds100bestcoffeeshops.com/wp-content/uploads/first.jpg"


def test_static_site_carries_shop_image_into_preview_payload(tmp_path: Path) -> None:
    data = tmp_path / "data" / "current_list.json"
    data.parent.mkdir()
    data.write_text(json.dumps([{
        "name": "First", "city": "Bogotá", "country": "Colombia", "rank": 1,
        "category": "South America",
        "image_url": "https://theworlds100bestcoffeeshops.com/wp-content/uploads/first.jpg",
    }]), encoding="utf-8")

    build_static_site(data, tmp_path / "site", tmp_path / "output.csv", tmp_path / "output.kml")

    index = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert '"image_url": "https://theworlds100bestcoffeeshops.com/wp-content/uploads/first.jpg"' in index
    assert 'id="detail-image"' in index
    assert "loadGoogleShopPhoto" in index
    assert "photo.authorAttributions" in index
    assert "photo.getURI({ maxWidth: 1200 })" in index
    assert "photo-1554118811" not in index
