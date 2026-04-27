import json

from ps_price_crawler.product import parse_product_detail

PRODUCT_ID = "UP1821-PPSA10990_00-1887411884729257"
PRODUCT_KEY = f"Product:{PRODUCT_ID}"
CONCEPT_KEY = "Concept:223118"


def _concept_payload() -> dict:
    return {
        "args": {"conceptId": "223118"},
        "cache": {
            PRODUCT_KEY: {
                "id": PRODUCT_ID,
                "__typename": "Product",
                "name": "Roblox (繁體中文)",
                "platforms": ["PS5"],
                "publisherName": "ROBLOX Corporation",
                "releaseDate": "2026-04-14T22:00:00Z",
                "topCategory": "GAME",
                "price": {
                    "basePrice": "免費",
                    "discountedPrice": "免費",
                    "isFree": True,
                    "serviceBranding": ["NONE"],
                },
            },
            CONCEPT_KEY: {
                "id": "223118",
                "__typename": "Concept",
                "name": "Roblox",
                "publisherName": "ROBLOX Corporation",
                "defaultProduct": {"__ref": PRODUCT_KEY},
                "releaseDate": {"value": "2023-10-10T21:00:00Z"},
            },
        },
    }


def _concept_html(env_payload: dict | None = None) -> str:
    if env_payload is None:
        env_payload = _concept_payload()
    return f"""
    <html>
      <script id=\"env:detail\" type=\"application/json\">{json.dumps(env_payload)}</script>
    </html>
    """


def test_parse_product_detail_from_env_cache():
    detail = parse_product_detail(_concept_html(), concept_id="223118")

    assert detail.concept_id == "223118"
    assert detail.concept_name == "Roblox"
    assert detail.product_id == "UP1821-PPSA10990_00-1887411884729257"
    assert detail.product_name == "Roblox (繁體中文)"
    assert detail.publisher_name == "ROBLOX Corporation"
    assert detail.release_date == "2026-04-14T22:00:00Z"
    assert detail.platforms == ("PS5",)
    assert detail.top_category == "GAME"
    assert detail.price is not None
    assert detail.price.is_free is True


def test_parse_product_detail_requires_default_product_ref():
    payload = _concept_payload()
    payload["cache"][CONCEPT_KEY]["defaultProduct"] = None

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "defaultProduct" in str(exc)
    else:
        raise AssertionError("Expected missing defaultProduct to raise ValueError")


def test_parse_product_detail_rejects_default_product_wrong_typename_ref():
    payload = _concept_payload()
    product = {**payload["cache"][PRODUCT_KEY], "id": "223118"}
    payload["cache"]["Product:223118"] = product
    payload["cache"][CONCEPT_KEY]["defaultProduct"] = {"__ref": "Concept:223118"}

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "defaultProduct" in str(exc)
    else:
        raise AssertionError("Expected invalid defaultProduct ref to raise ValueError")


def test_parse_product_detail_rejects_default_product_non_string_ref():
    payload = _concept_payload()
    product = {**payload["cache"][PRODUCT_KEY], "id": "223118"}
    payload["cache"]["Product:223118"] = product
    payload["cache"][CONCEPT_KEY]["defaultProduct"] = {"__ref": 223118}

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "defaultProduct" in str(exc)
    else:
        raise AssertionError("Expected non-string defaultProduct ref to raise ValueError")


def test_parse_product_detail_rejects_default_product_locale_suffixed_ref():
    payload = _concept_payload()
    payload["cache"][CONCEPT_KEY]["defaultProduct"] = {"__ref": f"{PRODUCT_KEY}:zh-hant-tw"}

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "defaultProduct" in str(exc)
    else:
        raise AssertionError("Expected locale-suffixed defaultProduct ref to raise ValueError")


def test_parse_product_detail_requires_referenced_product():
    payload = _concept_payload()
    payload["cache"]["Product:OTHER-PRODUCT"] = payload["cache"].pop(PRODUCT_KEY)

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert PRODUCT_ID in str(exc)
    else:
        raise AssertionError("Expected missing referenced product to raise ValueError")


def test_parse_product_detail_rejects_product_key_prefix_collision():
    payload = _concept_payload()
    payload["cache"][f"{PRODUCT_KEY}9"] = payload["cache"].pop(PRODUCT_KEY)

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert PRODUCT_ID in str(exc)
    else:
        raise AssertionError("Expected product key prefix collision to raise ValueError")


def test_parse_product_detail_rejects_concept_key_prefix_collision():
    payload = _concept_payload()
    payload["cache"]["Concept:2231189"] = payload["cache"].pop(CONCEPT_KEY)

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "223118" in str(exc)
    else:
        raise AssertionError("Expected concept key prefix collision to raise ValueError")


def test_parse_product_detail_prefers_exact_concept_key():
    payload = _concept_payload()
    exact_concept = payload["cache"].pop(CONCEPT_KEY)
    locale_concept = {**exact_concept, "name": "Locale Concept"}
    payload["cache"] = {
        "Concept:223118:zh-hant-tw": locale_concept,
        CONCEPT_KEY: exact_concept,
        PRODUCT_KEY: payload["cache"][PRODUCT_KEY],
    }

    detail = parse_product_detail(_concept_html(payload), concept_id="223118")

    assert detail.concept_name == "Roblox"


def test_parse_product_detail_rejects_multiple_locale_concept_keys_without_exact():
    payload = _concept_payload()
    exact_concept = payload["cache"].pop(CONCEPT_KEY)
    payload["cache"] = {
        "Concept:223118:zh-hant-tw": {**exact_concept, "name": "Locale Concept"},
        "Concept:223118:en-us": exact_concept,
        PRODUCT_KEY: payload["cache"][PRODUCT_KEY],
    }

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "Multiple Concept" in str(exc)
    else:
        raise AssertionError("Expected multiple locale concept keys to raise ValueError")


def test_parse_product_detail_prefers_exact_product_key():
    payload = _concept_payload()
    exact_product = payload["cache"].pop(PRODUCT_KEY)
    locale_product = {**exact_product, "name": "Locale Product"}
    payload["cache"] = {
        f"{PRODUCT_KEY}:zh-hant-tw": locale_product,
        PRODUCT_KEY: exact_product,
        CONCEPT_KEY: payload["cache"][CONCEPT_KEY],
    }

    detail = parse_product_detail(_concept_html(payload), concept_id="223118")

    assert detail.product_name == "Roblox (繁體中文)"


def test_parse_product_detail_rejects_multiple_locale_product_keys_without_exact():
    payload = _concept_payload()
    exact_product = payload["cache"].pop(PRODUCT_KEY)
    payload["cache"] = {
        f"{PRODUCT_KEY}:zh-hant-tw": {**exact_product, "name": "Locale Product"},
        f"{PRODUCT_KEY}:en-us": exact_product,
        CONCEPT_KEY: payload["cache"][CONCEPT_KEY],
    }

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "Multiple Product" in str(exc)
    else:
        raise AssertionError("Expected multiple locale product keys to raise ValueError")


def test_parse_product_detail_requires_concept_name():
    payload = _concept_payload()
    del payload["cache"][CONCEPT_KEY]["name"]

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "name" in str(exc)
    else:
        raise AssertionError("Expected missing concept name to raise ValueError")


def test_parse_product_detail_rejects_empty_concept_name():
    payload = _concept_payload()
    payload["cache"][CONCEPT_KEY]["name"] = ""

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "name" in str(exc)
    else:
        raise AssertionError("Expected empty concept name to raise ValueError")


def test_parse_product_detail_rejects_empty_product_id():
    payload = _concept_payload()
    payload["cache"][PRODUCT_KEY]["id"] = ""

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "id" in str(exc)
    else:
        raise AssertionError("Expected empty product id to raise ValueError")


def test_parse_product_detail_rejects_empty_product_name():
    payload = _concept_payload()
    payload["cache"][PRODUCT_KEY]["name"] = ""

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "name" in str(exc)
    else:
        raise AssertionError("Expected empty product name to raise ValueError")


def test_parse_product_detail_rejects_empty_platforms():
    payload = _concept_payload()
    payload["cache"][PRODUCT_KEY]["platforms"] = []

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "platforms" in str(exc)
    else:
        raise AssertionError("Expected empty platforms to raise ValueError")


def test_parse_product_detail_rejects_empty_top_category():
    payload = _concept_payload()
    payload["cache"][PRODUCT_KEY]["topCategory"] = ""

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "topCategory" in str(exc)
    else:
        raise AssertionError("Expected empty topCategory to raise ValueError")


def test_parse_product_detail_requires_publisher_name():
    payload = _concept_payload()
    del payload["cache"][PRODUCT_KEY]["publisherName"]
    del payload["cache"][CONCEPT_KEY]["publisherName"]

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "publisherName" in str(exc)
    else:
        raise AssertionError("Expected missing publisherName to raise ValueError")


def test_parse_product_detail_rejects_empty_product_publisher_before_concept_fallback():
    payload = _concept_payload()
    payload["cache"][PRODUCT_KEY]["publisherName"] = ""

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "publisherName" in str(exc)
    else:
        raise AssertionError("Expected empty product publisherName to raise before concept fallback")


def test_parse_product_detail_requires_release_date():
    payload = _concept_payload()
    del payload["cache"][PRODUCT_KEY]["releaseDate"]
    del payload["cache"][CONCEPT_KEY]["releaseDate"]

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "releaseDate" in str(exc)
    else:
        raise AssertionError("Expected missing releaseDate to raise ValueError")


def test_parse_product_detail_rejects_empty_product_release_date_before_concept_fallback():
    payload = _concept_payload()
    payload["cache"][PRODUCT_KEY]["releaseDate"] = ""

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "releaseDate" in str(exc)
    else:
        raise AssertionError("Expected empty product releaseDate to raise before concept fallback")


def test_parse_product_detail_requires_price():
    payload = _concept_payload()
    del payload["cache"][PRODUCT_KEY]["price"]

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "price" in str(exc)
    else:
        raise AssertionError("Expected missing price to raise ValueError")


def test_parse_product_detail_infers_free_price_from_download_cta():
    payload = _concept_payload()
    del payload["cache"][PRODUCT_KEY]["price"]
    payload["cache"][PRODUCT_KEY]["webctas"] = [{"type": "DOWNLOAD"}]

    detail = parse_product_detail(_concept_html(payload), concept_id="223118")

    assert detail.price is not None
    assert detail.price.is_free is True
    assert detail.price.discounted_price == "免費"


def test_parse_product_detail_rejects_empty_price():
    payload = _concept_payload()
    payload["cache"][PRODUCT_KEY]["price"] = {}

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "price" in str(exc)
    else:
        raise AssertionError("Expected empty price to raise ValueError")


def test_parse_product_detail_rejects_empty_product_price_before_concept_fallback():
    payload = _concept_payload()
    payload["cache"][PRODUCT_KEY]["price"] = {}
    payload["cache"][CONCEPT_KEY]["price"] = {
        "basePrice": "免費",
        "discountedPrice": "免費",
        "isFree": True,
        "serviceBranding": ["NONE"],
    }

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "price" in str(exc)
    else:
        raise AssertionError("Expected empty product price to raise before concept fallback")


def test_parse_product_detail_rejects_empty_concept_price_fallback():
    payload = _concept_payload()
    del payload["cache"][PRODUCT_KEY]["price"]
    payload["cache"][CONCEPT_KEY]["price"] = {}

    try:
        parse_product_detail(_concept_html(payload), concept_id="223118")
    except ValueError as exc:
        assert "price" in str(exc)
    else:
        raise AssertionError("Expected empty concept price fallback to raise ValueError")
