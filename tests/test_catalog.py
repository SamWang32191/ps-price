import json

from ps_price_crawler.catalog import parse_catalog_page


def _catalog_html() -> str:
    apollo_state = _catalog_apollo_state()
    next_data = {
        "props": {
            "pageProps": {
                "apolloState": apollo_state,
            }
        }
    }
    return _html_with_next_data(next_data)


def _catalog_apollo_state() -> dict:
    return {
        "CategoryGrid:28c9:zh-hant-tw:0:24": {
            "__typename": "CategoryGrid",
            "id": "28c9",
            "pageInfo": {
                "__typename": "PageInfo",
                "totalCount": 7988,
                "offset": 0,
                "size": 24,
                "isLast": False,
            },
            "concepts": [
                {"__ref": "Concept:223118:zh-hant-tw"},
                {"__ref": "Concept:10005069:zh-hant-tw"},
            ],
        },
        "Concept:223118:zh-hant-tw": {
            "__typename": "Concept",
            "id": "223118",
            "name": "Roblox",
            "price": {
                "__typename": "SkuPrice",
                "basePrice": "免費",
                "discountedPrice": "免費",
                "isFree": True,
                "serviceBranding": ["NONE"],
            },
            "media": [{"role": "MASTER", "url": "https://example.test/roblox.png"}],
            "products": [{"__ref": "Product:UP1821-PPSA10990_00-1887411884729257:zh-hant-tw"}],
        },
        "Concept:10005069:zh-hant-tw": {
            "__typename": "Concept",
            "id": "10005069",
            "name": "《沙羅週期》",
            "price": {
                "__typename": "SkuPrice",
                "basePrice": "NT$1,990",
                "discountedPrice": "NT$1,990",
                "isFree": False,
                "serviceBranding": ["NONE"],
            },
            "media": [],
            "products": [{"__ref": "Product:HP0000-PPSA00000_00-SAROS0000000000:zh-hant-tw"}],
        },
    }


def _html_with_next_data(next_data: dict) -> str:
    return f"""
    <html>
      <script id=\"__NEXT_DATA__\" type=\"application/json\">{json.dumps(next_data)}</script>
    </html>
    """


def test_parse_catalog_page_info():
    page = parse_catalog_page(_catalog_html(), source_url="https://store.playstation.com/zh-hant-tw/category/28c9/1")

    assert page.category_id == "28c9"
    assert page.total_count == 7988
    assert page.offset == 0
    assert page.size == 24
    assert page.is_last is False


def test_parse_catalog_concepts():
    page = parse_catalog_page(_catalog_html(), source_url="https://store.playstation.com/zh-hant-tw/category/28c9/1")

    assert [item.concept_id for item in page.items] == ["223118", "10005069"]
    assert page.items[0].name == "Roblox"
    assert page.items[0].product_ids == ("UP1821-PPSA10990_00-1887411884729257",)
    assert page.items[0].image_url == "https://example.test/roblox.png"
    assert page.items[0].price.discounted_price == "免費"
    assert page.items[0].price.is_free is True
    assert page.items[1].price.base_price == "NT$1,990"


def test_parse_catalog_selects_grid_matching_source_url():
    html = _catalog_html().replace(
        '"CategoryGrid:28c9:zh-hant-tw:0:24"',
        '"CategoryGrid:wrong:zh-hant-tw:0:24": {"id": "wrong", "pageInfo": {"totalCount": 1, "offset": 0, "size": 1, "isLast": true}, "concepts": []}, "CategoryGrid:28c9:zh-hant-tw:0:24"',
    )

    page = parse_catalog_page(html, source_url="https://store.playstation.com/zh-hant-tw/category/28c9/1")

    assert page.category_id == "28c9"
    assert page.total_count == 7988
    assert len(page.items) == 2


def test_parse_catalog_requires_page_info():
    html = _catalog_html().replace(
        '"pageInfo": {"__typename": "PageInfo", "totalCount": 7988, "offset": 0, "size": 24, "isLast": false},',
        "",
    )

    try:
        parse_catalog_page(html, source_url="https://store.playstation.com/zh-hant-tw/category/28c9/1")
    except ValueError as exc:
        assert "pageInfo" in str(exc)
    else:
        raise AssertionError("Expected missing pageInfo to raise ValueError")


def test_parse_catalog_requires_concept_refs():
    html = _catalog_html().replace(
        '"concepts": [{"__ref": "Concept:223118:zh-hant-tw"}, {"__ref": "Concept:10005069:zh-hant-tw"}]',
        '"concepts": null',
    )

    try:
        parse_catalog_page(html, source_url="https://store.playstation.com/zh-hant-tw/category/28c9/1")
    except ValueError as exc:
        assert "concepts" in str(exc)
    else:
        raise AssertionError("Expected missing concepts to raise ValueError")


def test_parse_catalog_reads_apollo_state_from_props():
    html = _html_with_next_data({"props": {"apolloState": _catalog_apollo_state()}})

    page = parse_catalog_page(html, source_url="https://store.playstation.com/zh-hant-tw/category/28c9/1")

    assert page.category_id == "28c9"
    assert len(page.items) == 2
