import io
import json
from urllib.error import URLError
from unittest.mock import patch

from src.geocoder import GeocodeResult, GooglePlacesGeocoder
from src.models import CoffeeShop


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_geocode_shop_returns_first_candidate() -> None:
    payload = {
        "status": "OK",
        "candidates": [
            {
                "place_id": "abc123",
                "formatted_address": "Godthabsvej 34B, 2000 Frederiksberg, Denmark",
                "geometry": {"location": {"lat": 55.686, "lng": 12.532}},
            }
        ],
    }

    with patch("urllib.request.urlopen", return_value=_FakeResponse(json.dumps(payload).encode())):
        geocoder = GooglePlacesGeocoder(api_key="test-key")
        shop = CoffeeShop(
            name="Coffee Collective",
            city="Frederiksberg",
            country="Denmark",
            rank=1,
            category="Top 100",
        )

        result = geocoder.geocode_shop(shop)

    assert result is not None
    assert result.place_id == "abc123"
    assert result.lat == 55.686
    assert result.lng == 12.532


def test_geocode_shop_returns_none_when_no_candidates() -> None:
    payload = {"status": "ZERO_RESULTS", "candidates": []}
    geocode_payload = {"status": "ZERO_RESULTS", "results": []}

    def _urlopen_side_effect(url: str, timeout: float = 30.0):
        if "findplacefromtext" in url:
            return _FakeResponse(json.dumps(payload).encode())
        return _FakeResponse(json.dumps(geocode_payload).encode())

    with patch("urllib.request.urlopen", side_effect=_urlopen_side_effect):
        geocoder = GooglePlacesGeocoder(api_key="test-key")
        shop = CoffeeShop(
            name="Unknown",
            city="Nowhere",
            country="Noland",
            rank=1,
            category="Top 100",
        )

        result = geocoder.geocode_shop(shop)

    assert result is None
    assert geocoder.last_status == "ZERO_RESULTS"


def test_geocode_shop_prefers_address_queries_before_name_city_country() -> None:
    captured_queries: list[str] = []

    def _geocode_text_side_effect(query: str):
        captured_queries.append(query)
        if "101 E Walnut Ave Rogers, AR 72756, USA" in query:
            return GeocodeResult(
                lat=36.3353,
                lng=-94.1186,
                place_id="onyx123",
                formatted_address="101 E Walnut Ave, Rogers, AR 72756, USA",
            )
        return None

    geocoder = GooglePlacesGeocoder(api_key="test-key")
    shop = CoffeeShop(
        name="Onyx Coffee LAB",
        city="Rogers",
        country="USA",
        rank=1,
        category="Top 100",
        address="101 E Walnut Ave Rogers, AR 72756, USA",
    )

    with patch.object(geocoder, "geocode_text", side_effect=_geocode_text_side_effect):
        result = geocoder.geocode_shop(shop)

    assert result is not None
    assert captured_queries[0] == "Onyx Coffee LAB, 101 E Walnut Ave Rogers, AR 72756, USA"


def test_geocode_shop_falls_back_to_geocoding_api_when_places_has_zero_results() -> None:
    places_payload = {"status": "ZERO_RESULTS", "candidates": []}
    geocode_payload = {
        "status": "OK",
        "results": [
            {
                "place_id": "geo123",
                "formatted_address": "R. dos Sapateiros 111, 1100-619 Lisboa, Portugal",
                "geometry": {"location": {"lat": 38.71066, "lng": -9.13922}},
            }
        ],
    }

    with patch(
        "urllib.request.urlopen",
        side_effect=[
            _FakeResponse(json.dumps(places_payload).encode()),
            _FakeResponse(json.dumps(geocode_payload).encode()),
        ],
    ):
        geocoder = GooglePlacesGeocoder(api_key="test-key")
        shop = CoffeeShop(
            name="The Folks",
            city="Lisboa",
            country="Portugal",
            rank=88,
            category="Top 100",
        )

        result = geocoder.geocode_shop(shop)

    assert result is not None
    assert result.place_id == "geo123"
    assert result.lat == 38.71066
    assert result.lng == -9.13922
    assert geocoder.last_status == "OK"


def test_geocode_shop_retries_and_recovers_on_transient_error() -> None:
    payload = {
        "status": "OK",
        "candidates": [
            {
                "place_id": "abc123",
                "formatted_address": "Godthabsvej 34B, 2000 Frederiksberg, Denmark",
                "geometry": {"location": {"lat": 55.686, "lng": 12.532}},
            }
        ],
    }
    sleeper_calls: list[float] = []

    with patch(
        "urllib.request.urlopen",
        side_effect=[URLError("temporary"), _FakeResponse(json.dumps(payload).encode())],
    ):
        geocoder = GooglePlacesGeocoder(
            api_key="test-key",
            max_retries=2,
            retry_delay_seconds=0.5,
            sleeper=sleeper_calls.append,
        )
        shop = CoffeeShop(
            name="Coffee Collective",
            city="Frederiksberg",
            country="Denmark",
            rank=1,
            category="Top 100",
        )

        result = geocoder.geocode_shop(shop)

    assert result is not None
    assert result.place_id == "abc123"
    assert sleeper_calls == [0.5]


def test_geocode_shop_returns_none_after_retry_exhaustion() -> None:
    sleeper_calls: list[float] = []

    with patch("urllib.request.urlopen", side_effect=URLError("always down")):
        geocoder = GooglePlacesGeocoder(
            api_key="test-key",
            max_retries=2,
            retry_delay_seconds=0.25,
            sleeper=sleeper_calls.append,
        )
        shop = CoffeeShop(
            name="Coffee Collective",
            city="Copenhagen",
            country="Denmark",
            rank=1,
            category="Top 100",
        )

        result = geocoder.geocode_shop(shop)

    assert result is None
    assert sleeper_calls == [0.25]
    assert geocoder.last_status == "NETWORK_ERROR"
    assert "always down" in geocoder.last_error_message


def test_geocode_shop_rejects_country_mismatch_and_uses_next_query() -> None:
    geocoder = GooglePlacesGeocoder(api_key="test-key")
    shop = CoffeeShop(
        name="Little Victories Coffee",
        city="",
        country="Canada",
        rank=71,
        category="Top 100",
        address="44 Elgin St, Ottawa, Ontario K1P 1C7",
    )

    wrong_result = GeocodeResult(
        lat=15.507472,
        lng=-88.0440769,
        place_id="ChIJCxDm1HNbZo8RoTPNIwbOvww",
        formatted_address="Boulevard Los Próceres, San Pedro Sula, Cortés, Honduras",
    )
    correct_result = GeocodeResult(
        lat=45.4229,
        lng=-75.6908,
        place_id="ChIJfQxQ0G4FzkwR0tq6f_0f6f8",
        formatted_address="44 Elgin St, Ottawa, ON K1P 1C7, Canada",
    )

    with patch.object(geocoder, "geocode_text", side_effect=[wrong_result, correct_result]) as mocked:
        result = geocoder.geocode_shop(shop)

    assert result == correct_result
    assert mocked.call_count == 2


def test_geocode_shop_rejects_another_branch_in_the_same_country() -> None:
    geocoder = GooglePlacesGeocoder(api_key="test-key")
    shop = CoffeeShop(
        name="Simón Coffee",
        city="Medellín",
        country="Colombia",
        rank=80,
        category="South America",
        address="Cra. 37 #10-54, El Poblado, Medellín, Colombia",
    )
    wrong_branch = GeocodeResult(
        lat=6.2,
        lng=-75.6,
        place_id="wrong-branch",
        formatted_address="Cl. 45 #12-78, Laureles, Medellín, Colombia",
    )
    correct_branch = GeocodeResult(
        lat=6.21,
        lng=-75.57,
        place_id="correct-branch",
        formatted_address="Cra. 37 #10-54, El Poblado, Medellín, Colombia",
    )

    with patch.object(geocoder, "geocode_text", side_effect=[wrong_branch, correct_branch]) as mocked:
        result = geocoder.geocode_shop(shop)

    assert result == correct_branch
    assert mocked.call_count == 2


def test_geocode_shop_rejects_blank_formatted_address() -> None:
    geocoder = GooglePlacesGeocoder(api_key="test-key")
    shop = CoffeeShop(
        name="Mr Wush Wush", city="Ibagué", country="Colombia", rank=72, category="South America"
    )
    blank_result = GeocodeResult(lat=4.4, lng=-75.2, place_id="unknown", formatted_address="")

    with patch.object(geocoder, "geocode_text", return_value=blank_result):
        result = geocoder.geocode_shop(shop)

    assert result is None


def test_rituales_does_not_accept_the_wrong_circular_with_same_building_number() -> None:
    geocoder = GooglePlacesGeocoder(api_key="test-key")
    shop = CoffeeShop(
        name="Rituales Compañía de Café",
        city="Medellín",
        country="Colombia",
        rank=64,
        category="South America",
        address="Circular 74A #39B-22, Laureles, Medellín, Colombia",
    )
    wrong_road = GeocodeResult(
        lat=6.2,
        lng=-75.6,
        place_id="wrong-circular",
        formatted_address="Cq. 6 #39B-22, Laureles, Medellín, Colombia",
    )
    correct_road = GeocodeResult(
        lat=6.25,
        lng=-75.59,
        place_id="right-circular",
        formatted_address="Cq. 74A #39B-22, Laureles, Medellín, Colombia",
    )

    with patch.object(geocoder, "geocode_text", side_effect=[wrong_road, correct_road]):
        result = geocoder.geocode_shop(shop)

    assert result == correct_road
