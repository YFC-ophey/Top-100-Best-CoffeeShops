"""Which missing place_ids still count as a gap worth chasing.

`update_map.yml` opens a reminder issue whenever a shop has no `place_id`.
Two shops have never resolved across repeated owner-geocode runs, so that
reminder reopened on every schedule and stopped carrying information. They are
accepted as-is: both still render in the list with the address the source
publishes and a working Google Maps link, and Little Victories keeps its pin
from the coordinates it already has.
"""

from __future__ import annotations

from src.category_utils import normalize_category

# (category, rank) of shops accepted without a place_id. Remove an entry here
# the moment a geocode run resolves it, so the reminder starts working again.
ACCEPTED_WITHOUT_PLACE_ID: frozenset[tuple[str, int]] = frozenset(
    {
        ("Top 100", 71),  # Little Victories Coffee, Ottawa — has coordinates, no place_id
        ("Top 100", 100),  # Vacation Coffee, Melbourne — no coordinates either
    }
)


def count_actionable_place_id_gaps(rows: list[dict[str, object]]) -> int:
    """Shops missing a place_id that an owner-geocode run could still fix."""
    return sum(1 for row in rows if _is_actionable_gap(row))


def _is_actionable_gap(row: dict[str, object]) -> bool:
    if row.get("place_id"):
        return False
    key = (normalize_category(str(row.get("category", ""))), int(row.get("rank", 0)))
    return key not in ACCEPTED_WITHOUT_PLACE_ID
