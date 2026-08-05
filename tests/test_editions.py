import json
from pathlib import Path

from src import main as src_main
from src.category_utils import CURRENT_EDITION_YEAR, normalize_edition_year
from src.models import CoffeeShop
from src.state import has_shop_changes, load_previous_state
from src.web_app import _build_overview_filters, _build_overview_shops, _shop_id


def _shop(
    name: str = "Shop",
    rank: int = 1,
    category: str = "Top 100",
    edition_year: int = CURRENT_EDITION_YEAR,
) -> CoffeeShop:
    return CoffeeShop(
        name=name,
        city="Oslo",
        country="Norway",
        rank=rank,
        category=category,
        edition_year=edition_year,
    )


class TestEditionYearNormalization:
    def test_rows_written_before_the_edition_field_existed_default_to_current(
        self, tmp_path: Path
    ) -> None:
        data_file = tmp_path / "current_list.json"
        legacy_row = {
            "name": "Tim Wendelboe",
            "city": "",
            "country": "Norway",
            "rank": 2,
            "category": "Top 100",
        }
        data_file.write_text(json.dumps([legacy_row]), encoding="utf-8")

        shops = load_previous_state(data_file)

        assert shops[0].edition_year == CURRENT_EDITION_YEAR

    def test_coerces_string_years_and_falls_back_on_junk(self) -> None:
        assert normalize_edition_year("2025") == 2025
        assert normalize_edition_year(None) == CURRENT_EDITION_YEAR
        assert normalize_edition_year("") == CURRENT_EDITION_YEAR
        assert normalize_edition_year("not-a-year") == CURRENT_EDITION_YEAR


class TestEditionChangeDetection:
    def test_same_shop_in_a_new_edition_counts_as_a_change(self) -> None:
        previous = [_shop(edition_year=2026)]
        current = [_shop(edition_year=2027)]

        assert has_shop_changes(previous, current) is True

    def test_identical_edition_is_not_a_change(self) -> None:
        assert has_shop_changes([_shop()], [_shop()]) is False


class TestArchivedEditions:
    def test_previous_edition_is_retained_when_a_new_one_is_scraped(self) -> None:
        previous = [_shop(name="Last Year", edition_year=2026)]
        scraped = [_shop(name="This Year", edition_year=2027)]

        merged = src_main._merge_with_archived_editions(previous, scraped)

        assert [shop.name for shop in merged] == ["This Year", "Last Year"]
        assert sorted({shop.edition_year for shop in merged}) == [2026, 2027]

    def test_rescraping_the_same_edition_replaces_rather_than_duplicates(self) -> None:
        previous = [_shop(name="Stale", edition_year=2026)]
        scraped = [_shop(name="Fresh", edition_year=2026)]

        merged = src_main._merge_with_archived_editions(previous, scraped)

        assert [shop.name for shop in merged] == ["Fresh"]


class TestCollapseGuardAcrossEditions:
    def test_new_edition_year_does_not_trip_the_guard(self) -> None:
        previous = [_shop(name=f"S{i}", rank=i + 1, edition_year=2026) for i in range(100)]
        current = [_shop(name=f"S{i}", rank=i + 1, edition_year=2027) for i in range(100)]

        # A healthy new edition replaces every row with a different year; the
        # guard must judge it against last year's count, not find zero.
        src_main._guard_against_scrape_collapse(previous, current)

    def test_still_catches_a_real_collapse_in_a_new_edition(self) -> None:
        previous = [_shop(name=f"S{i}", rank=i + 1, edition_year=2026) for i in range(100)]
        current = [_shop(name=f"S{i}", rank=i + 1, edition_year=2027) for i in range(10)]

        try:
            src_main._guard_against_scrape_collapse(previous, current)
        except RuntimeError as error:
            assert "Scrape collapse" in str(error)
        else:  # pragma: no cover - failure path
            raise AssertionError("expected the guard to reject a 100 -> 10 scrape")


class TestEditionFilters:
    def test_filters_expose_every_edition_newest_first_and_all_active(self) -> None:
        shops = [
            _shop(name="New", edition_year=2027),
            _shop(name="Old A", rank=2, edition_year=2026),
            _shop(name="Old B", rank=3, edition_year=2026),
        ]
        overview_shops, _ = _build_overview_shops(shops)

        filters = _build_overview_filters(overview_shops, [])

        assert [edition["key"] for edition in filters["editions"]] == [2027, 2026]
        assert [edition["count"] for edition in filters["editions"]] == [1, 2]
        assert filters["defaults"]["active_editions"] == [2027, 2026]

    def test_single_edition_dataset_yields_one_chip(self) -> None:
        overview_shops, _ = _build_overview_shops([_shop()])

        filters = _build_overview_filters(overview_shops, [])

        assert [edition["key"] for edition in filters["editions"]] == [CURRENT_EDITION_YEAR]

    def test_overview_rows_carry_the_edition_year(self) -> None:
        overview_shops, _ = _build_overview_shops([_shop(edition_year=2025)])

        assert overview_shops[0]["edition_year"] == 2025


class TestShopIdentity:
    def test_same_rank_in_two_editions_gets_distinct_ids(self) -> None:
        first = _shop(name="Onyx Coffee LAB", edition_year=2026)
        second = _shop(name="Onyx Coffee LAB", edition_year=2027)

        assert _shop_id(first) != _shop_id(second)
