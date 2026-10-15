from dataclasses import dataclass
import html
import json
import re
import time
from typing import Callable
from urllib.error import URLError
from urllib.parse import urlencode
import urllib.request
import unicodedata

from src.country_centroids import UNKNOWN_COUNTRY, normalize_country
from src.models import CoffeeShop


@dataclass(slots=True)
class GeocodeResult:
    lat: float
    lng: float
    place_id: str
    formatted_address: str


class GooglePlacesGeocoder:
    def __init__(
        self,
        api_key: str,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
        rate_limit_seconds: float = 0.0,
        timeout_seconds: float = 30.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout_seconds = timeout_seconds
        self.sleeper = sleeper
        self.last_status = ""
        self.last_error_message = ""

    def geocode_text(self, query: str) -> GeocodeResult | None:
        self.last_status = ""
        self.last_error_message = ""
        place_result = self._find_place_from_text(query)
        if place_result:
            return place_result

        # Fallback to Geocoding API when Places text search does not return a candidate.
        if self.last_status in {"ZERO_RESULTS", "NOT_FOUND", "MISSING_GEOMETRY", "UNKNOWN"}:
            geocode_result = self._geocode_address(query)
            if geocode_result:
                return geocode_result

        return None

    def _find_place_from_text(self, query: str) -> GeocodeResult | None:
        params = urlencode(
            {
                "input": query,
                "inputtype": "textquery",
                "fields": "place_id,formatted_address,geometry",
                "key": self.api_key,
            }
        )
        url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?{params}"
        payload = self._request_json(url)
        if payload is None:
            return None
        return self._extract_result(payload, "candidates")

    def _geocode_address(self, query: str) -> GeocodeResult | None:
        params = urlencode({"address": query, "key": self.api_key})
        url = f"https://maps.googleapis.com/maps/api/geocode/json?{params}"
        payload = self._request_json(url)
        if payload is None:
            return None
        return self._extract_result(payload, "results")

    def _request_json(self, url: str) -> dict[str, object] | None:
        payload: dict[str, object] | None = None
        for attempt in range(self.max_retries):
            try:
                if self.rate_limit_seconds > 0:
                    self.sleeper(self.rate_limit_seconds)
                with urllib.request.urlopen(url, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except URLError as error:
                self.last_status = "NETWORK_ERROR"
                self.last_error_message = str(error.reason or error)
                if attempt == (self.max_retries - 1):
                    return None
                self.sleeper(self.retry_delay_seconds)
            except TimeoutError as error:
                self.last_status = "TIMEOUT"
                self.last_error_message = str(error)
                if attempt == (self.max_retries - 1):
                    return None
                self.sleeper(self.retry_delay_seconds)
            except json.JSONDecodeError as error:
                self.last_status = "INVALID_JSON"
                self.last_error_message = str(error)
                if attempt == (self.max_retries - 1):
                    return None
                self.sleeper(self.retry_delay_seconds)
        return payload

    def _extract_result(self, payload: dict[str, object], collection_key: str) -> GeocodeResult | None:
        payload_status = str(payload.get("status", "")).strip().upper()
        payload_error = str(payload.get("error_message", "")).strip()
        self.last_status = payload_status or self.last_status or "UNKNOWN"
        self.last_error_message = payload_error or self.last_error_message

        candidates = payload.get(collection_key, [])
        if not candidates:
            return None

        candidate = candidates[0]
        location = candidate.get("geometry", {}).get("location", {})
        if "lat" not in location or "lng" not in location:
            self.last_status = "MISSING_GEOMETRY"
            return None

        return GeocodeResult(
            lat=float(location["lat"]),
            lng=float(location["lng"]),
            place_id=str(candidate.get("place_id", "")),
            formatted_address=str(candidate.get("formatted_address", "")),
        )

    def geocode_shop(self, shop: CoffeeShop) -> GeocodeResult | None:
        for query in self._shop_queries(shop):
            result = self.geocode_text(query)
            if result and self._result_matches_shop(shop, result):
                return result
        return None

    def _shop_queries(self, shop: CoffeeShop) -> list[str]:
        name = self._clean_text(shop.name)
        city = self._clean_text(shop.city)
        country = self._clean_text(shop.country)
        address = self._clean_text(shop.address)
        formatted_address = self._clean_text(shop.formatted_address)

        queries: list[str] = []
        if address:
            if name:
                queries.append(f"{name}, {address}")
            queries.append(address)
        if formatted_address:
            if name:
                queries.append(f"{name}, {formatted_address}")
            queries.append(formatted_address)
        if name and city and country:
            queries.append(f"{name}, {city}, {country}")
        elif name and country:
            queries.append(f"{name}, {country}")
        elif name:
            queries.append(name)

        unique_queries: list[str] = []
        seen: set[str] = set()
        for query in queries:
            normalized = query.casefold()
            if not query or normalized in seen:
                continue
            seen.add(normalized)
            unique_queries.append(query)
        return unique_queries

    @staticmethod
    def _clean_text(value: str | None) -> str:
        if not value:
            return ""
        return " ".join(html.unescape(str(value)).split()).strip()

    def _result_matches_shop(self, shop: CoffeeShop, result: GeocodeResult) -> bool:
        formatted_address = self._clean_text(result.formatted_address)
        if not formatted_address:
            return False

        if shop.address:
            if self._normalized_phrase(shop.country) == "colombia":
                source_road = self._colombian_road_anchor(shop.address)
                resolved_road = self._colombian_road_anchor(formatted_address)
                if source_road and resolved_road and source_road != resolved_road:
                    return False
            return self._address_overlap_ok(
                shop.address, formatted_address, locality=f"{shop.city} {shop.country}"
            )

        # A country match identifies far too many candidates for a shop without
        # an address. Require the returned place to at least be in its city.
        expected_country, unknown_country = normalize_country(shop.country)
        if not unknown_country and expected_country != UNKNOWN_COUNTRY:
            if not self._country_matches_formatted(expected_country, formatted_address):
                return False
        city = self._normalized_phrase(shop.city)
        resolved = self._normalized_phrase(formatted_address)
        return bool(city and f" {city} " in f" {resolved} ")

    def _address_overlap_ok(
        self, source_address: str | None, resolved_address: str, locality: str = ""
    ) -> bool:
        if self._normalized_phrase(source_address) == self._normalized_phrase(resolved_address):
            return True
        source_tokens = self._address_tokens(source_address)
        resolved_tokens = self._address_tokens(resolved_address)
        if not source_tokens or not resolved_tokens:
            return False

        # City and country occur in every nearby branch; they cannot establish
        # that a returned place is at the shop's street address.
        locality_tokens = self._address_tokens(locality)
        source_tokens -= locality_tokens
        resolved_tokens -= locality_tokens
        if not source_tokens or not resolved_tokens:
            return False

        overlap = source_tokens & resolved_tokens
        if len(overlap) >= 2:
            return True

        union = source_tokens | resolved_tokens
        if not union:
            return False
        return (len(overlap) / len(union)) >= 0.18

    def _country_matches_formatted(self, expected_country: str, formatted_address: str) -> bool:
        normalized_formatted = self._normalized_phrase(formatted_address)
        if not normalized_formatted:
            return False

        expected_norm = self._normalized_phrase(expected_country)
        if not expected_norm:
            return False

        aliases = _COUNTRY_TEXT_ALIASES.get(expected_norm, {expected_norm})
        haystack = f" {normalized_formatted} "
        return any(f" {alias} " in haystack for alias in aliases)

    def _address_tokens(self, value: str | None) -> set[str]:
        normalized = self._normalized_phrase(value)
        if not normalized:
            return set()
        return {
            token
            for token in normalized.split()
            if (len(token) >= 3 or (len(token) >= 2 and token.isdigit()))
            and token not in _GENERIC_ADDRESS_TOKENS
        }

    @staticmethod
    def _colombian_road_anchor(value: str | None) -> tuple[str, str] | None:
        normalized = GooglePlacesGeocoder._normalized_phrase(value)
        match = re.search(
            r"(?:^| )(circular|cq|carrera|cra|calle|cl|avenida|av|transversal|tv) (\d+[a-z]?)\b",
            normalized,
        )
        if not match:
            return None
        road_type = {
            "cq": "circular",
            "cra": "carrera",
            "cl": "calle",
            "av": "avenida",
            "tv": "transversal",
        }.get(match.group(1), match.group(1))
        return road_type, match.group(2)

    @staticmethod
    def _normalized_phrase(value: str | None) -> str:
        text = GooglePlacesGeocoder._clean_text(value)
        if not text:
            return ""
        normalized = unicodedata.normalize("NFKD", text.casefold())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


_GENERIC_ADDRESS_TOKENS = {
    "street",
    "st",
    "road",
    "rd",
    "avenue",
    "ave",
    "boulevard",
    "blvd",
    "city",
    "region",
    "state",
    "building",
    "unit",
    "shop",
    "coffee",
    "cafe",
    "specialty",
}

_COUNTRY_TEXT_ALIASES: dict[str, set[str]] = {
    "usa": {"usa", "united states", "united states of america"},
    "united kingdom": {"united kingdom", "uk", "great britain", "england", "scotland"},
    "uae": {"uae", "united arab emirates"},
    "mexico": {"mexico", "mexico"},
    "turkey": {"turkey", "turkiye"},
    "czech republic": {"czech republic", "czechia"},
    "republic of korea": {"republic of korea", "south korea", "korea"},
}
