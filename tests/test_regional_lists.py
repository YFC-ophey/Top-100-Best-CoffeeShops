from src.models import CoffeeShop
from src.scraper import SOURCE_URLS, parse_coffee_shops
from src.web_app import _build_overview_countries, _build_overview_filters, _build_overview_shops


def test_regional_card_missing_country_does_not_consume_next_shop():
    def card(rank, name, country):
        url = f'https://theworlds100bestcoffeeshops.com/locales-europe/shop-{rank}/'
        return (f'<p class="elementor-heading-title"><a href="{url}">{rank}</a></p>'
                f'<h1 class="elementor-heading-title"><a href="{url}">{name}</a></h1>'
                + (f'<p class="elementor-heading-title"><a href="{url}">{country}</a></p>' if country else ''))
    rows = parse_coffee_shops(card(68, 'DABOV', '') + card(69, 'Conway', 'Ireland'), 'Europe')
    assert [(r.rank, r.name, r.country) for r in rows] == [(68, 'DABOV', ''), (69, 'Conway', 'Ireland')]


def test_new_regions_are_scraped_and_visible_by_default():
    regions = ['Europe', 'North, Central America and the Caribbean']
    assert all(region in SOURCE_URLS for region in regions)
    shops = [CoffeeShop(name='Example', city='Oslo', country='Norway', rank=1, category=region) for region in regions]
    overview, _ = _build_overview_shops(shops)
    filters = _build_overview_filters(overview, _build_overview_countries(overview))
    assert set(regions) <= set(filters['defaults']['active_categories'])
    assert all(any(c['key'] == region and c['count'] == 1 for c in filters['categories']) for region in regions)


def test_all_published_countries_have_real_map_centers():
    from pathlib import Path
    from src.country_centroids import COUNTRY_CENTROIDS, UNKNOWN_COUNTRY, normalize_country
    from src.state import load_previous_state

    rows = load_previous_state(Path(__file__).resolve().parents[1] / 'data/current_list.json')
    for row in rows:
        country, _ = normalize_country(row.country)
        if country != UNKNOWN_COUNTRY:
            assert country in COUNTRY_CENTROIDS, country
            assert COUNTRY_CENTROIDS[country] != COUNTRY_CENTROIDS[UNKNOWN_COUNTRY]


def test_regional_csv_keeps_source_address_without_geocoding(tmp_path):
    import csv
    from src.generator import generate_csv

    shop = CoffeeShop(name='Example', city='Oslo', country='Norway', rank=1,
                      category='Europe', address='Example Street 1, Oslo')
    target = tmp_path / 'shops.csv'
    generate_csv([shop], target)
    with target.open() as handle:
        row = next(csv.DictReader(handle))
    assert row['formatted_address'] == shop.address
    assert row['lat'] == ''
    assert row['lng'] == ''
