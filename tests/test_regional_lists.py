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
    regions = ['Europe', 'North, Central America and the Caribbean', 'Asia-Pacific']
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


def test_asia_pacific_preserves_published_tie_and_country_typo():
    from pathlib import Path
    from src.country_centroids import normalize_country

    fixture = Path(__file__).parent / 'fixtures/asia-pacific-cards.html'
    rows = parse_coffee_shops(fixture.read_text(), 'Asia-Pacific')
    assert [(r.rank, r.name) for r in rows] == [
        (11, 'Koffee Mameya Kakeru'), (11, 'C4 Coffee Co.'), (46, 'Ignis'),
    ]
    assert normalize_country(rows[-1].country) == ('Japan', False)
    assert normalize_country('South Korea') == ('Republic of Korea', False)


def test_asia_pacific_release_has_one_verified_pin_per_published_shop():
    import json
    from src.country_centroids import normalize_country
    from src.main import _carry_forward_geocode
    from src.data_corrections import apply_verified_shop_corrections
    from src.web_app import _load_shops

    root = __import__('pathlib').Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'docs/location-audits/asia-pacific-2026.json').read_text())
    evidence = {r['source_url']: r for r in manifest['records']}
    shops = [s for s in _load_shops(root / 'data/current_list.json')
             if s.category == 'Asia-Pacific' and s.edition_year == 2026]
    assert len(shops) == len(evidence) == 100
    assert sorted(s.rank for s in shops) == sorted([r for r in range(1, 101) if r != 12] + [11])
    overview, quality = _build_overview_shops(shops)
    assert len({s['id'] for s in overview}) == 100  # Both #11 shops remain selectable.
    assert quality['unknown_country_count'] == quality['missing_city_count'] == 0
    bounds = {
        'Australia': (-44, -10, 112, 154), 'New Zealand': (-48, -34, 165, 179),
        'Japan': (30, 46, 129, 146), 'Republic of Korea': (33, 39, 124, 132),
        'China': (18, 54, 73, 135), 'Hong Kong': (22, 23, 113, 115),
        'Taiwan': (21, 26, 119, 123), 'Malaysia': (0, 8, 99, 120),
        'Singapore': (1.1, 1.5, 103.6, 104.1), 'Indonesia': (-12, 7, 94, 142),
        'Thailand': (5, 21, 97, 106), 'The Philippines': (4, 22, 116, 127),
        'Vietnam': (8, 24, 102, 110), 'India': (6, 38, 68, 98),
    }
    for shop in shops:
        proof = evidence[shop.source_url]
        assert proof['status'] == 'verified' and proof['map_url']
        assert shop.lat == proof['lat'] and shop.lng == proof['lng']
        assert shop.place_id == proof['place_id']
        south, north, west, east = bounds[normalize_country(shop.country)[0]]
        assert south <= shop.lat <= north and west <= shop.lng <= east, shop.name
        # The weekly source refresh must retain every verified pin.
        fresh = CoffeeShop(name=shop.name, city=shop.city, country=shop.country,
                           category=shop.category, rank=shop.rank, address=proof['published_address'],
                           source_url=shop.source_url)
        apply_verified_shop_corrections([fresh])
        restored = _carry_forward_geocode([shop], [fresh])[0]
        assert (restored.lat, restored.lng) == (shop.lat, shop.lng), shop.name


def test_shanghai_directions_use_verified_pin_instead_of_wrong_name_match():
    from src.data_corrections import apply_verified_shop_corrections
    from src.web_app import _mobile_maps_link
    from urllib.parse import parse_qs, urlparse

    for rank, name, coords in [(18, 'Coffee Enough', '31.233511,121.463432'),
                               (48, 'Blacksheep Espresso', '31.215375,121.461899')]:
        shop = CoffeeShop(name=name, city='Shanghai', country='China', rank=rank, category='Asia-Pacific')
        apply_verified_shop_corrections([shop])
        assert parse_qs(urlparse(_mobile_maps_link(shop)).query)['destination'] == [coords]
