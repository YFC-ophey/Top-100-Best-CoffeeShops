from src.scraper import extract_city_address, parse_coffee_shops


def test_parse_coffee_shops_extracts_rank_name_and_location() -> None:
    html = """
    <html><body>
      <ol>
        <li>1. Coffee Collective - Copenhagen, Denmark</li>
        <li>2. Proud Mary - Melbourne, Australia</li>
      </ol>
    </body></html>
    """

    shops = parse_coffee_shops(html, category="Top 100")

    assert len(shops) == 2
    assert shops[0].rank == 1
    assert shops[0].name == "Coffee Collective"
    assert shops[0].city == "Copenhagen"
    assert shops[0].country == "Denmark"
    assert shops[0].category == "Top 100"


def test_parse_coffee_shops_skips_unparseable_entries() -> None:
    html = """
    <html><body>
      <ol>
        <li>Not a ranked item</li>
        <li>3. Tim Wendelboe - Oslo, Norway</li>
      </ol>
    </body></html>
    """

    shops = parse_coffee_shops(html, category="Top 100")

    assert len(shops) == 1
    assert shops[0].name == "Tim Wendelboe"


def test_parse_coffee_shops_extracts_from_elementor_loop_cards() -> None:
    html = """
    <div data-elementor-type="loop-item" class="e-loop-item">
      <p class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/onyx-coffee-lab/">1</a></p>
      <h1 class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/onyx-coffee-lab/">Onyx Coffee LAB</a></h1>
      <p class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/onyx-coffee-lab/">USA</a></p>
    </div>
    <div data-elementor-type="loop-item" class="e-loop-item">
      <p class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/tim-wendelboe/">2</a></p>
      <h1 class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/tim-wendelboe/">Tim Wendelboe</a></h1>
      <p class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/tim-wendelboe/">Norway</a></p>
    </div>
    """

    shops = parse_coffee_shops(html, category="Top 100")

    assert len(shops) == 2
    assert shops[0].rank == 1
    assert shops[0].name == "Onyx Coffee LAB"
    assert shops[0].country == "USA"
    assert shops[0].source_url == "https://theworlds100bestcoffeeshops.com/locales/onyx-coffee-lab/"


def test_parse_coffee_shops_decodes_html_entities_in_loop_cards() -> None:
    html = """
    <div data-elementor-type="loop-item" class="e-loop-item">
      <p class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/tobbys-estate/">5</a></p>
      <h1 class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/tobbys-estate/">Toby&#8217;s Estate Coffee Roasters</a></h1>
      <p class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/tobbys-estate/">Australia</a></p>
    </div>
    <div data-elementor-type="loop-item" class="e-loop-item">
      <p class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/fika-and-co/">61</a></p>
      <h1 class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/fika-and-co/">Fika &amp; Co. Cafe</a></h1>
      <p class="elementor-heading-title"><a href="https://theworlds100bestcoffeeshops.com/locales/fika-and-co/">Canada</a></p>
    </div>
    """

    shops = parse_coffee_shops(html, category="Top 100")

    assert [shop.name for shop in shops] == [
        "Toby’s Estate Coffee Roasters",
        "Fika & Co. Cafe",
    ]


def _detail_page(*headings: str) -> str:
    blocks = "".join(
        f'<p class="elementor-heading-title elementor-size-default">{text}</p>'
        for text in headings
    )
    return f"<html><body>{blocks}</body></html>"


def test_extract_city_address_reads_single_word_city() -> None:
    html = _detail_page("Oslo", "Norway", "Grüners Gate 1, 0552 Oslo, Norway", "https://timwendelboe.no/")

    city, address = extract_city_address(html, fallback_country="Norway")

    assert city == "Oslo"
    assert address == "Grüners Gate 1, 0552 Oslo, Norway"


def test_extract_city_address_reads_address_without_street_number() -> None:
    html = _detail_page(
        "Addis Ababa",
        "Ethiopia",
        "Jacros - Salite Mehret Rd, Addis Ababa, Ethiopia",
        "https://www.galanicoffee.com/",
    )

    city, address = extract_city_address(html, fallback_country="Ethiopia")

    assert city == "Addis Ababa"
    assert address == "Jacros - Salite Mehret Rd, Addis Ababa, Ethiopia"


def test_extract_city_address_prefers_heading_over_description_prose() -> None:
    html = (
        '<meta property="og:description" content="Mulano is located in the south of '
        'Ecuador in a city of 25,000 inhabitants called Piñas." />'
        + _detail_page("Piñas", "Ecuador", "Avenida Loja, Piñas, Ecuador")
    )

    city, address = extract_city_address(html, fallback_country="Ecuador")

    assert city == "Piñas"
    assert address == "Avenida Loja, Piñas, Ecuador"


def test_extract_city_address_ignores_urls_after_country() -> None:
    html = _detail_page("Sydney", "Australia", "https://www.tobysestate.com.au/")

    city, address = extract_city_address(html, fallback_country="Australia")

    assert city == "Sydney"
    assert address is None


def test_extract_city_address_rejects_prose_city_candidate() -> None:
    html = _detail_page(
        "a small town somewhere in the far south of the country", "Ecuador", "Avenida Loja, Ecuador"
    )

    city, _address = extract_city_address(html, fallback_country="Ecuador")

    assert city is None


def test_extract_city_address_handles_a_city_state() -> None:
    """Singapore's locale pages repeat the name as both city and country."""
    html = _detail_page(
        "Singapore",
        "Singapore",
        "139, Selegie Road, Singapore, 18309, Singapore",
        "https://apartmentcoffee.co/",
    )

    city, address = extract_city_address(html, fallback_country="Singapore")

    assert city == "Singapore"
    assert address == "139, Selegie Road, Singapore, 18309, Singapore"


def test_extract_city_address_collapses_source_whitespace() -> None:
    html = _detail_page("Natales,  Región de Magallanes", "Chile", "Bulnes  411, Natales, Chile")

    city, address = extract_city_address(html, fallback_country="Chile")

    assert city == "Natales, Región de Magallanes"
    assert address == "Bulnes 411, Natales, Chile"
