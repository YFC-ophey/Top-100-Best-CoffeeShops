from html.parser import HTMLParser
import html
import re
import time
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from src.category_utils import CURRENT_EDITION_YEAR
from src.models import CoffeeShop

USER_AGENT = (
    "Mozilla/5.0 (compatible; RoastMapBot/1.0; "
    "+https://github.com/YFC-ophey/Top-100-Best-CoffeeShops)"
)

SOURCE_URLS: dict[str, str] = {
    "Top 100": "https://theworlds100bestcoffeeshops.com/top-100-coffee-shops/",
    "South America": "https://theworlds100bestcoffeeshops.com/top-100-coffee-shops-south/",
    "Europe": "https://theworlds100bestcoffeeshops.com/top-100-coffee-shops-europe/",
    "North, Central America and the Caribbean": "https://theworlds100bestcoffeeshops.com/top-100-coffee-shops-north/",
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
    r'<a href="(?P<href>https://theworlds100bestcoffeeshops\.com/locales(?:-[a-z]+)?/[^"]+/)">(?P<text>.*?)</a>',
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
_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)
_SPACE_PATTERN = re.compile(r"\s+")
_SOURCE_HOST = "theworlds100bestcoffeeshops.com"

# "Santa Cruz de la Sierra" and "Ho Chi Minh City" are real; a 12-word sentence
# lifted from a page's prose is not.
_MAX_CITY_LENGTH = 60
_MAX_CITY_WORDS = 6
_MIN_ADDRESS_LENGTH = 10


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


def _official_image_url(value: str | None) -> str | None:
    """Only accept the ranking site's uploaded images, never tracking or sponsor art."""
    url = html.unescape(value or "").strip()
    parsed = urlparse(url)
    if (
        parsed.scheme in {"http", "https"}
        and parsed.hostname in {_SOURCE_HOST, f"www.{_SOURCE_HOST}"}
        and parsed.path.startswith("/wp-content/uploads/")
        and parsed.path.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ):
        return url
    return None


class _ShopImageParser(HTMLParser):
    """Associate a featured image with its own shop link on ranking pages."""

    def __init__(self) -> None:
        super().__init__()
        self.images: dict[str, str] = {}
        self._link: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a":
            href = html.unescape(attributes.get("href") or "").strip()
            parsed = urlparse(href)
            self._link = href if parsed.hostname in {_SOURCE_HOST, f"www.{_SOURCE_HOST}"} and parsed.path.startswith("/locales") else None
        elif tag == "img" and self._link and self._link not in self.images:
            image = _official_image_url(attributes.get("src") or attributes.get("data-src"))
            if image:
                self.images[self._link] = image

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._link = None


class _OpenGraphImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.image_url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta" or self.image_url:
            return
        attributes = dict(attrs)
        if (attributes.get("property") or "").lower() == "og:image":
            self.image_url = _official_image_url(attributes.get("content"))


def extract_shop_image(detail_html: str) -> str | None:
    parser = _OpenGraphImageParser()
    parser.feed(detail_html)
    return parser.image_url


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


def parse_coffee_shops(
    html: str, category: str, edition_year: int = CURRENT_EDITION_YEAR
) -> list[CoffeeShop]:
    shops = _parse_legacy_list_items(html, category, edition_year)
    if not shops:
        shops = _parse_elementor_loop_cards(html, category, edition_year)
    image_parser = _ShopImageParser()
    image_parser.feed(html)
    for shop in shops:
        if shop.source_url:
            shop.image_url = image_parser.images.get(shop.source_url)
    return shops


def _parse_legacy_list_items(html: str, category: str, edition_year: int) -> list[CoffeeShop]:
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
                edition_year=edition_year,
            )
        )
    return shops


def _parse_elementor_loop_cards(html: str, category: str, edition_year: int) -> list[CoffeeShop]:
    primary = _parse_elementor_loop_cards_primary(html, category, edition_year)
    fallback = _parse_elementor_loop_cards_by_href(html, category, edition_year)
    if fallback and len(fallback) >= len(primary):
        # Group by the shop URL so absent fields cannot consume the next card.
        return fallback
    return primary


def _parse_elementor_loop_cards_primary(
    html: str, category: str, edition_year: int
) -> list[CoffeeShop]:
    shops: list[CoffeeShop] = []
    for match in _LOOP_CARD_PATTERN.finditer(html):
        shops.append(
            CoffeeShop(
                name=_unescape(match.group("name")),
                city="",
                country=_unescape(match.group("country")),
                rank=int(match.group("rank")),
                category=category,
                edition_year=edition_year,
                source_url=match.group("href").strip(),
            )
        )
    return sorted(shops, key=lambda value: value.rank)


def _parse_elementor_loop_cards_by_href(
    html_content: str, category: str, edition_year: int
) -> list[CoffeeShop]:
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
        if rank is None or name is None:
            continue
        shops.append(
            CoffeeShop(
                name=name,
                city="",
                country=country or "",
                rank=rank,
                category=category,
                edition_year=edition_year,
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
            if not shop.image_url:
                shop.image_url = extract_shop_image(detail_html)
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
    """Read the city and street address off a locale detail page.

    Every locale page renders the same heading triplet in order — city,
    country, address — followed by the shop's website and socials. Anchoring on
    the country heading is what makes single-word cities ("Oslo") and addresses
    with no street number ("Jacros - Salite Mehret Rd, Addis Ababa, Ethiopia")
    readable; the older shape-based heuristics silently dropped both.
    """
    heading_texts = _extract_heading_texts(detail_html)
    country_idx = _find_country_index(heading_texts, fallback_country)

    city = None
    address = None
    if country_idx is not None:
        if country_idx > 0:
            city = _city_candidate(heading_texts[country_idx - 1])
        address = _address_candidate(heading_texts[country_idx + 1 :])

    if address is None:
        address = _address_candidate(heading_texts)
    if city is None:
        city = _extract_city_from_description(detail_html)

    return city, address


def _find_country_index(heading_texts: list[str], country: str) -> int | None:
    target = country.casefold().strip()
    if not target:
        return None
    matches = [
        idx for idx, text in enumerate(heading_texts) if text.casefold().strip() == target
    ]
    if not matches:
        return None
    # A city-state repeats the name in both slots ("Singapore", "Singapore");
    # the later heading is the country one, leaving the city readable above it.
    return matches[-1]


def _city_candidate(text: str) -> str | None:
    """Accept a place label, reject a URL or a sentence of marketing prose."""
    value = text.strip(" \t\r\n,")
    if not value or _URL_PATTERN.match(value):
        return None
    if any(char.isdigit() for char in value):
        return None
    if len(value) > _MAX_CITY_LENGTH or len(value.split()) > _MAX_CITY_WORDS:
        return None
    return value


def _address_candidate(heading_texts: list[str]) -> str | None:
    for text in heading_texts:
        value = text.strip(" \t\r\n,")
        if not value or _URL_PATTERN.match(value):
            continue
        if len(value) <= _MIN_ADDRESS_LENGTH:
            continue
        if "," not in value and not any(char.isdigit() for char in value):
            continue
        return value
    return None


def _unescape(value: str) -> str:
    """Source markup carries numeric entities (&#8217;, &#8211;) in shop names."""
    return html.unescape(value).strip()


def _extract_heading_texts(detail_html: str) -> list[str]:
    values: list[str] = []
    for match in _HEADING_TEXT_PATTERN.finditer(detail_html):
        text = _TAG_STRIPPER.sub("", match.group("text"))
        text = _SPACE_PATTERN.sub(" ", html.unescape(text)).strip()
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
