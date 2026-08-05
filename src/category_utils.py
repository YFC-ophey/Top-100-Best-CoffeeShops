from __future__ import annotations

TOP_100_CATEGORY = "Top 100"
SOUTH_AMERICA_CATEGORY = "South America"

# The source publishes one ranking per year, announced each February. Rows
# scraped without an explicit year belong to the edition currently on the
# source pages; bump this when the next edition is released.
CURRENT_EDITION_YEAR = 2026


def normalize_category(category: str | None) -> str:
    if category is None:
        return ""
    cleaned = category.strip()
    lowered = cleaned.casefold()
    if lowered in {"south", "south america"}:
        return SOUTH_AMERICA_CATEGORY
    if lowered == "top 100":
        return TOP_100_CATEGORY
    return cleaned


def normalize_edition_year(year: int | str | None) -> int:
    """Coerce a stored edition year to an int, falling back to the current one.

    Rows committed before the edition dimension existed carry no year at all,
    so they resolve to the edition that was live when they were scraped.
    """
    if year is None or year == "":
        return CURRENT_EDITION_YEAR
    try:
        return int(year)
    except (TypeError, ValueError):
        return CURRENT_EDITION_YEAR
