from html.parser import HTMLParser
import html
import re
import time
from urllib.request import Request, urlopen

from src.models import CoffeeShop

USER_AGENT = (
    "Mozilla/5.0 (compatible; RoastMapBot/1.0; "
    "+https://github.com/YFC-ophey/Top-100-Best-CoffeeShops)"
)

SOURCE_URLS: dict[str, str] = {
    "Top 100": "https://theworlds100bestcoffeeshops.com/top-100-coffee-shops/",
    "South America": "https://theworlds100bestcoffeeshops.com/top-100-coffee-shops-south/",
}

_ITEM_PATTERN = re.compile(
    r"^\s*(?P<rank>\d{1,3})[\).:-]?\s+(?P<name>[^-]+?)\s+-\s+(?P<city>[^,]+),\s*(?P<country>.+)\s*$"
)
_LOOP_CARD_PATTERN = re.compile(
    r'<p class="elementor-heading-title[^"]*">\s*<a href="(?P<href>[^"]+)">\s*(?P<rank>\d{1,3})\s*</a>\s*</p>'
    r".*?"
    r'<h1 class="elementor-heading-title[^"]*">\s*<a href="[^"]+">\s*(?P<name>[^<]+?)\s*</a>\s*</h1>'
    r".*?"
    r'<p class="elementor-heading-title[^"]*">\s*<a href="[^"]+">\s*(?P<country>[^<]+?)\s*</a>\s*</p>',
    re.DOTALL,
)
_LOCALE_LINK_PATTERN = re.compile(
    r'<a href="(?P<href>https://theworlds100bestcoffeeshops\.com/locales/[^"]+/)">(?P<text>.*?)</a>',
    re.DOTALL,
)
_TAG_STRIPPER = re.compile(r"<[^>]+>")
_HEADING_TEXT_PATTERN = re.compile(
    r'<p class="elementor-heading-title[^"]*">\s*(?P<text>.*?)\s*</p>',
    re.DOTALL,
)
_META_OG_DESCRIPTION_PATTERN = re.compile(
    r'<meta property="og:description" content="(?P<desc>[^"]+)"',
    re.IGNORECASE,
)
_CITY_FROM_DESCRIPTION_PATTERN = re.compile(
    r"located in (?P<city>[^,.]+(?:,\s*[^,.]+)?)",
    re.IGNORECASE,
)


class _ListItemParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._inside_li = False
        self._buffer: list[str] = []
        self.items: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "li":
            self._inside_li = True
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._inside_li:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "li" and self._inside_li:
            text = " ".join(part.strip() for part in self._buffer if part.strip())
            if text:
                self.items.append(text)
            self._inside_li = False
            self._buffer = []


def fetch_html(
    url: str,
    timeout_seconds: int = 30,
    retries: int = 3,
    backoff_seconds: float = 2.0,
    sleeper=time.sleep,
) -> str:
    """Fetch a list page with a real User-Agent and linear-backoff retries.

    A transient network error or a UA-based block on the source's hosting must
    not fail the whole weekly pipeline run.
    """
    last_error: OSError | None = None
    for attempt in range(retries):
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return response.read().decode("utf-8", errors="ignore")
        except OSError as error:  # URLError, HTTPError, socket timeout
            last_error = error
            if attempt < retries - 1:
                sleeper(backoff_seconds * (attempt + 1))
    raise last_error if last_error is not None else OSError(f"fetch failed: {url}")


def parse_coffee_shops(html: str, category: str) -> list[CoffeeShop]:
    shops = _parse_legacy_list_items(html, category)
    if shops:
        return shops
    return _parse_elementor_loop_cards(html, category)


def _parse_legacy_list_items(html: str, category: str) -> list[CoffeeShop]:
    parser = _ListItemParser()
    parser.feed(html)
    shops: list[CoffeeShop] = []
    for item in parser.items:
        match = _ITEM_PATTERN.match(item)
        if not match:
            continue
        shops.append(
            CoffeeShop(
                name=match.group("name").strip(),
                city=match.group("city").strip(),
                country=match.group("country").strip(),
                rank=int(match.group("rank")),
                category=category,
            )
        )
    return shops


def _parse_elementor_loop_cards(html: str, category: str) -> list[CoffeeShop]:
    primary = _parse_elementor_loop_cards_primary(html, category)
    fallback = _parse_elementor_loop_cards_by_href(html, category)
    if len(fallback) > len(primary):
        return fallback
    return primary


def _parse_elementor_loop_cards_primary(html: str, category: str) -> list[CoffeeShop]:
    shops: list[CoffeeShop] = []
    for match in _LOOP_CARD_PATTERN.finditer(html):
        shops.append(
            CoffeeShop(
                name=match.group("name").strip(),
                city="",
                country=match.group("country").strip(),
                rank=int(match.group("rank")),
                category=category,
                source_url=match.group("href").strip(),
            )
        )
    return sorted(shops, key=lambda value: value.rank)


def _parse_elementor_loop_cards_by_href(html_content: str, category: str) -> list[CoffeeShop]:
    links: list[tuple[str, str]] = []
    for match in _LOCALE_LINK_PATTERN.finditer(html_content):
        href = match.group("href").strip()
        raw_text = _TAG_STRIPPER.sub("", match.group("text"))
        text = html.unescape(raw_text).strip()
        if text:
            links.append((href, text))

    grouped: list[tuple[str, list[str]]] = []
    current_href: str | None = None
    current_texts: list[str] = []
    for href, text in links:
        if current_href is None:
            current_href = href
        if href != current_href:
            grouped.append((current_href, current_texts))
            current_href = href
            current_texts = []
        current_texts.append(text)
    if current_href is not None:
        grouped.append((current_href, current_texts))

    shops: list[CoffeeShop] = []
    for href, texts in grouped:
        rank: int | None = None
        name: str | None = None
        country: str | None = None
        non_numeric: list[str] = []
        for text in texts:
            if rank is None and text.isdigit():
                rank = int(text)
            elif not text.isdigit():
                non_numeric.append(text)
        if non_numeric:
            name = non_numeric[0]
        if len(non_numeric) > 1:
            country = non_numeric[1]
        if rank is None or name is None or country is None:
            continue
        shops.append(
            CoffeeShop(
                name=name,
                city="",
                country=country,
                rank=rank,
                category=category,
                source_url=href,
            )
        )
    return sorted(shops, key=lambda value: value.rank)


def enrich_shops_with_details(
    shops: list[CoffeeShop],
    fetcher=fetch_html,
    sleep_seconds: float = 1.0,
    retries: int = 2,
) -> list[CoffeeShop]:
    enriched: list[CoffeeShop] = []
    for shop in shops:
        if not shop.source_url:
            enriched.append(shop)
            continue
        detail_html = _fetch_with_retry(shop.source_url, fetcher, retries=retries)
        if detail_html:
            city, address = extract_city_address(detail_html, fallback_country=shop.country)
            if city:
                shop.city = city
            if address:
                shop.address = address
        enriched.append(shop)
        time.sleep(sleep_seconds)
    return enriched


def _fetch_with_retry(url: str, fetcher, retries: int) -> str | None:
    for attempt in range(retries + 1):
        try:
            return fetcher(url)
        except Exception:
            if attempt == retries:
                return None
            time.sleep(0.5)
    return None


def extract_city_address(detail_html: str, fallback_country: str) -> tuple[str | None, str | None]:
    heading_texts = _extract_heading_texts(detail_html)

    country_idx = None
    for idx, text in enumerate(heading_texts):
        if text.casefold() == fallback_country.casefold():
            country_idx = idx
            break

    city = None
    if country_idx is not None and country_idx > 0:
        candidate = heading_texts[country_idx - 1]
        if "," in candidate and not any(char.isdigit() for char in candidate):
            city = candidate

    address = None
    for text in heading_texts:
        # heuristic: full addresses usually contain numbers and commas
        if any(char.isdigit() for char in text) and "," in text and len(text) > 10:
            address = text
            break

    if city is None:
        city = _extract_city_from_description(detail_html)

    return city, address


def _extract_heading_texts(detail_html: str) -> list[str]:
    values: list[str] = []
    for match in _HEADING_TEXT_PATTERN.finditer(detail_html):
        text = _TAG_STRIPPER.sub("", match.group("text"))
        text = html.unescape(text).strip()
        if text:
            values.append(text)
    return values


def _extract_city_from_description(detail_html: str) -> str | None:
    match = _META_OG_DESCRIPTION_PATTERN.search(detail_html)
    if not match:
        return None
    description = html.unescape(match.group("desc"))
    city_match = _CITY_FROM_DESCRIPTION_PATTERN.search(description)
    if not city_match:
        return None
    return city_match.group("city").strip()
