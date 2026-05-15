import hashlib
import json
from pathlib import Path

from ps_price_crawler.models import PriceInfo
from ps_price_crawler.price_contract import normalize_price_info
from ps_price_crawler.product import parse_product_detail


FIXTURE_DIR = Path("tests/fixtures/ps_store")

EXPECTED_FIXTURES = {
    "free": {"concept_id": "10012874", "state": "FREE", "parser_error": None},
    "paid_full_price": {
        "concept_id": "10002075",
        "state": "PAID",
        "parser_error": {"type": "ValueError", "message": "Missing required Product.price"},
    },
    "discounted_paid": {
        "concept_id": "231761",
        "state": "DISCOUNTED",
        "parser_error": {"type": "ValueError", "message": "Missing required Product.price"},
    },
    "ps_plus_candidate": {
        "concept_id": "10014149",
        "state": "PS_PLUS",
        "parser_error": {"type": "ValueError", "message": "Missing required Product.price"},
    },
    "missing_or_unavailable_candidate": {
        "concept_id": "10014992",
        "state": "UNKNOWN",
        "parser_error": {"type": "ValueError", "message": "Missing required Concept.defaultProduct"},
    },
}

REQUIRED_TOP_LEVEL_FIELDS = {
    "target_key",
    "concept_id",
    "name",
    "source_url",
    "catalog_price_fields",
    "normalized_state",
    "raw_html_sha256",
    "raw_html_size_bytes",
    "raw_html_committed",
    "product_detail",
    "parser_error",
}


def _fixture_payloads() -> list[dict]:
    assert FIXTURE_DIR.is_dir(), f"Missing fixture directory: {FIXTURE_DIR}"
    json_files = sorted(FIXTURE_DIR.glob("concept_*.json"))
    assert json_files, f"No committed fixture JSON files found in {FIXTURE_DIR}"
    return [json.loads(path.read_text(encoding="utf-8")) for path in json_files]


def _catalog_price_from_fixture(fixture: dict) -> PriceInfo | None:
    fields = fixture["catalog_price_fields"]
    if fields["basePrice"] is None and fields["discountedPrice"] is None:
        return None
    return PriceInfo(
        base_price=fields["basePrice"],
        discounted_price=fields["discountedPrice"],
        discount_text=fields["discountText"],
        is_free=bool(fields["isFree"]),
        is_exclusive=bool(fields["isExclusive"]),
        is_tied_to_subscription=bool(fields["isTiedToSubscription"]),
        service_branding=tuple(fields["serviceBranding"]),
        upsell_text=fields["upsellText"],
    )


def test_committed_fixture_set_covers_required_target_keys_and_states():
    fixtures = _fixture_payloads()

    by_key = {fixture["target_key"]: fixture for fixture in fixtures}

    assert set(by_key) == set(EXPECTED_FIXTURES)
    assert len(fixtures) == len(EXPECTED_FIXTURES)

    for target_key, expected in EXPECTED_FIXTURES.items():
        fixture = by_key[target_key]
        assert REQUIRED_TOP_LEVEL_FIELDS <= set(fixture), target_key
        assert fixture["concept_id"] == expected["concept_id"]
        assert fixture["normalized_state"] == expected["state"]
        assert fixture["catalog_price_fields"]["normalizedState"] == expected["state"]
        assert fixture["name"]
        assert fixture["source_url"].startswith("https://store.playstation.com/")


def test_raw_html_metadata_matches_committed_html_or_documents_omission():
    for fixture in _fixture_payloads():
        size = fixture["raw_html_size_bytes"]
        digest = fixture["raw_html_sha256"]

        assert isinstance(size, int) and size > 0
        assert isinstance(digest, str) and len(digest) == 64

        if fixture["raw_html_committed"]:
            html_path = FIXTURE_DIR / fixture["raw_html_fixture"]
            raw_html = html_path.read_bytes()
            assert len(raw_html) == size
            assert hashlib.sha256(raw_html).hexdigest() == digest
            assert fixture.get("raw_html_omitted_reason") is None
        else:
            assert fixture["raw_html_omitted_reason"]


def test_fixture_parser_outcomes_are_explicit_without_tracebacks():
    fixtures = _fixture_payloads()

    for fixture in fixtures:
        expected = EXPECTED_FIXTURES[fixture["target_key"]]
        parser_error = fixture["parser_error"]

        if expected["parser_error"] is None:
            assert parser_error is None, fixture["target_key"]
            detail = fixture["product_detail"]
            assert detail["concept_id"] == fixture["concept_id"]
            assert detail["product_id"]
            assert detail["product_name"]
            assert detail["price_fields"]["normalizedState"]
            continue

        assert parser_error == expected["parser_error"]
        assert fixture["product_detail"] is None
        assert "Traceback" not in parser_error["message"]


def test_fixture_html_normalizes_price_states_with_catalog_evidence():
    for fixture in _fixture_payloads():
        catalog_price = _catalog_price_from_fixture(fixture)
        catalog_normalized = normalize_price_info(
            catalog_price,
            source="catalog",
            raw_missing_reason="Catalog item price block missing" if catalog_price is None else None,
        )

        assert catalog_normalized.state.value == fixture["normalized_state"]

        if not fixture["raw_html_committed"]:
            continue

        html = (FIXTURE_DIR / fixture["raw_html_fixture"]).read_text(encoding="utf-8")
        try:
            detail = parse_product_detail(
                html,
                concept_id=fixture["concept_id"],
                catalog_price=catalog_price,
            )
        except Exception as exc:
            assert fixture["target_key"] == "missing_or_unavailable_candidate"
            assert type(exc).__name__ == "MissingRequiredFieldError"
            assert "Concept.defaultProduct" in str(exc)
            continue

        normalized = normalize_price_info(detail.price, source="product_detail")
        assert normalized.state.value == fixture["normalized_state"]
