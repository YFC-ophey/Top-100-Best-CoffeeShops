import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src import main as src_main
from src.models import CoffeeShop
from src.scraper import fetch_html


def _shops(category: str, count: int) -> list[CoffeeShop]:
    return [
        CoffeeShop(name=f"Shop {i}", city="X", country="Y", rank=i + 1, category=category)
        for i in range(count)
    ]


class TestScrapeCollapseGuard:
    def test_aborts_when_a_category_shrinks_past_the_floor(self) -> None:
        with pytest.raises(RuntimeError, match="Scrape collapse"):
            src_main._guard_against_scrape_collapse(_shops("Top 100", 100), _shops("Top 100", 40))

    def test_allows_normal_annual_churn(self) -> None:
        src_main._guard_against_scrape_collapse(_shops("Top 100", 100), _shops("Top 100", 95))

    def test_allows_first_run_with_no_previous_state(self) -> None:
        src_main._guard_against_scrape_collapse([], _shops("Top 100", 5))

    def test_env_override_bypasses_the_guard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SCRAPE_ALLOW_SHRINK", "1")
        src_main._guard_against_scrape_collapse(_shops("Top 100", 100), _shops("Top 100", 1))

    def test_missing_category_counts_as_collapse(self) -> None:
        with pytest.raises(RuntimeError, match="South America"):
            src_main._guard_against_scrape_collapse(
                _shops("Top 100", 100) + _shops("South America", 100),
                _shops("Top 100", 100),
            )


class TestMetadataProvenance:
    def test_save_state_writes_metadata(self, tmp_path: Path) -> None:
        data_file = tmp_path / "data" / "current_list.json"
        metadata_file = tmp_path / "data" / "metadata.json"
        shops = _shops("Top 100", 3)
        shops[0].lat = 1.0
        shops[0].lng = 2.0
        with patch.object(src_main, "DATA_FILE", data_file), patch.object(
            src_main, "METADATA_FILE", metadata_file
        ):
            src_main._save_state(shops)

        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        assert metadata["total_shops"] == 3
        assert metadata["counts_by_category"] == {"Top 100": 3}
        assert metadata["geocoded_shops"] == 1
        assert metadata["updated_at_utc"].endswith("Z")
        assert "theworlds100bestcoffeeshops.com" in str(metadata["sources"])


class TestFetchHtmlRetry:
    def test_retries_transient_errors_then_succeeds(self) -> None:
        calls = {"n": 0}
        sleeps: list[float] = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b"<html>ok</html>"

        def fake_urlopen(request, timeout):
            calls["n"] += 1
            if calls["n"] < 3:
                raise OSError("boom")
            assert request.get_header("User-agent", "").startswith("Mozilla/5.0")
            return FakeResponse()

        with patch("src.scraper.urlopen", fake_urlopen):
            html = fetch_html("https://example.com", sleeper=sleeps.append)

        assert html == "<html>ok</html>"
        assert calls["n"] == 3
        assert sleeps == [2.0, 4.0]

    def test_raises_after_exhausting_retries(self) -> None:
        def always_fail(request, timeout):
            raise OSError("down")

        with patch("src.scraper.urlopen", always_fail):
            with pytest.raises(OSError, match="down"):
                fetch_html("https://example.com", retries=2, sleeper=lambda _: None)
