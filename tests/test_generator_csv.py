from pathlib import Path

from src.generator import generate_csv
from src.models import CoffeeShop


def test_generate_csv_writes_expected_header_and_rows(tmp_path: Path) -> None:
    shops = [
        CoffeeShop(name="Coffee Collective", city="Copenhagen", country="Denmark", rank=1, category="Top 100"),
        CoffeeShop(name="Proud Mary", city="Melbourne", country="Australia", rank=2, category="South America"),
    ]
    output_path = tmp_path / "coffee_shops.csv"

    generate_csv(shops, output_path)

    text = output_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()]
    assert (
        lines[0]
        == "rank,name,city,country,category,edition_year,lat,lng,place_id,formatted_address"
    )
    assert "1,Coffee Collective,Copenhagen,Denmark,Top 100,2026" in lines[1]
    assert "2,Proud Mary,Melbourne,Australia,South America,2026" in lines[2]


def test_generate_csv_orders_newest_edition_first(tmp_path: Path) -> None:
    shops = [
        CoffeeShop(
            name="Older Winner",
            city="Copenhagen",
            country="Denmark",
            rank=1,
            category="Top 100",
            edition_year=2025,
        ),
        CoffeeShop(
            name="Coffee Collective",
            city="Copenhagen",
            country="Denmark",
            rank=1,
            category="Top 100",
            edition_year=2026,
        ),
    ]
    output_path = tmp_path / "coffee_shops.csv"

    generate_csv(shops, output_path)

    lines = [line.strip() for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert "Coffee Collective" in lines[1]
    assert "Older Winner" in lines[2]
