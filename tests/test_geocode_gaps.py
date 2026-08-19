from src.geocode_gaps import ACCEPTED_WITHOUT_PLACE_ID, count_actionable_place_id_gaps


def test_accepted_shops_do_not_count_as_a_gap() -> None:
    rows = [
        {"category": "Top 100", "rank": 71, "name": "Little Victories Coffee", "place_id": None},
        {"category": "Top 100", "rank": 100, "name": "Vacation Coffee", "place_id": ""},
    ]

    assert count_actionable_place_id_gaps(rows) == 0


def test_a_new_missing_place_id_still_counts() -> None:
    rows = [
        {"category": "Top 100", "rank": 71, "name": "Little Victories Coffee", "place_id": None},
        {"category": "South America", "rank": 5, "name": "Somewhere New", "place_id": None},
    ]

    assert count_actionable_place_id_gaps(rows) == 1


def test_resolved_shops_never_count() -> None:
    rows = [{"category": "Top 100", "rank": 1, "name": "Onyx Coffee LAB", "place_id": "abc123"}]

    assert count_actionable_place_id_gaps(rows) == 0


def test_category_spelling_variants_still_match_the_accept_list() -> None:
    rows = [{"category": "top 100", "rank": 100, "name": "Vacation Coffee", "place_id": None}]

    assert count_actionable_place_id_gaps(rows) == 0


def test_accept_list_stays_small() -> None:
    """A growing list means geocoding is quietly degrading, not that more shops
    are legitimately unresolvable."""
    assert len(ACCEPTED_WITHOUT_PLACE_ID) <= 5
