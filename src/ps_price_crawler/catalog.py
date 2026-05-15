from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from ps_price_crawler.errors import (
    AmbiguousCacheEntryError,
    CrawlerParseError,
    MissingEmbeddedStateError,
    MissingRequiredFieldError,
)
from ps_price_crawler.models import CatalogItem, CatalogPage, PriceInfo
from ps_price_crawler.next_data import extract_embedded_state
from ps_price_crawler.price_contract import NormalizedPrice, normalize_price_info


def parse_catalog_page(html: str, source_url: str) -> CatalogPage:
    state = extract_embedded_state(html)
    props = state.next_data.get("props", {})
    page_props = props.get("pageProps", {}) if isinstance(props, dict) else {}
    apollo_state = page_props.get("apolloState") if isinstance(page_props, dict) else None
    if apollo_state is None and isinstance(props, dict):
        apollo_state = props.get("apolloState", {})
    if not isinstance(apollo_state, dict):
        raise MissingRequiredFieldError("Missing required catalog page apolloState")

    source_category_id = _category_id_from_source_url(source_url)
    grid_key, grid = _find_category_grid(apollo_state, source_category_id)
    page_info = _required_mapping(grid, "pageInfo", "CategoryGrid")
    concept_refs = _required_list(grid, "concepts", "CategoryGrid")
    items = tuple(_catalog_item_from_ref(apollo_state, ref) for ref in concept_refs)
    _reject_duplicate_catalog_items(items)

    return CatalogPage(
        source_url=source_url,
        category_id=str(grid.get("id") or _category_id_from_key(grid_key)),
        total_count=_required_int(page_info, "totalCount", "pageInfo"),
        offset=_required_int(page_info, "offset", "pageInfo"),
        size=_required_int(page_info, "size", "pageInfo"),
        is_last=bool(_required_value(page_info, "isLast", "pageInfo")),
        items=items,
    )


def normalize_catalog_item_price(item: CatalogItem) -> NormalizedPrice:
    return normalize_price_info(
        item.price,
        source="catalog",
        raw_missing_reason="Catalog item price block missing" if item.price is None else None,
    )


def _find_category_grid(
    apollo_state: dict[str, Any], source_category_id: str | None
) -> tuple[str, dict[str, Any]]:
    matches: list[tuple[str, dict[str, Any]]] = []
    for key, value in apollo_state.items():
        if key.startswith("CategoryGrid:") and isinstance(value, dict):
            matches.append((key, value))

    if source_category_id is not None:
        for key, value in matches:
            grid_category_id = str(value.get("id") or _category_id_from_key(key))
            if grid_category_id == source_category_id:
                return key, value

    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise MissingEmbeddedStateError("Catalog page does not contain a CategoryGrid entry")
    raise AmbiguousCacheEntryError("Catalog page contains multiple CategoryGrid entries but none matched source URL")


def _category_id_from_source_url(source_url: str) -> str | None:
    parts = [part for part in urlparse(source_url).path.split("/") if part]
    try:
        category_index = parts.index("category")
    except ValueError:
        return None
    if category_index + 1 >= len(parts):
        return None
    return parts[category_index + 1]


def _category_id_from_key(key: str) -> str:
    parts = key.split(":")
    if len(parts) < 2:
        raise CrawlerParseError(f"Cannot parse CategoryGrid key: {key}")
    return parts[1]


def _catalog_item_from_ref(apollo_state: dict[str, Any], ref: dict[str, str]) -> CatalogItem:
    concept_key = _required_value(ref, "__ref", "concept ref")
    concept = _required_mapping(apollo_state, str(concept_key), "apolloState")
    product_ids = _product_ids_from_concept(concept, str(concept_key))
    return CatalogItem(
        concept_id=str(_required_value(concept, "id", str(concept_key))),
        name=str(_required_value(concept, "name", str(concept_key))),
        product_ids=product_ids,
        image_url=_master_image_url(concept),
        price=_price_info(concept.get("price")),
    )


def _reject_duplicate_catalog_items(items: tuple[CatalogItem, ...]) -> None:
    seen: set[str] = set()
    for item in items:
        identifier = f"Concept:{item.concept_id}"
        if identifier in seen:
            raise AmbiguousCacheEntryError(f"Duplicate {identifier} catalog entry")
        seen.add(identifier)


def _product_ids_from_concept(concept: dict[str, Any], context: str) -> tuple[str, ...]:
    product_refs = concept.get("products", [])
    if product_refs is None:
        return ()
    if not isinstance(product_refs, list):
        raise MissingRequiredFieldError(f"Expected {context}.products to be a list")

    product_ids = tuple(_product_id_from_ref(product_ref, context) for product_ref in product_refs)
    _reject_duplicate_product_ids(product_ids, context)
    return product_ids


def _product_id_from_ref(product_ref: Any, context: str) -> str:
    if not isinstance(product_ref, dict):
        raise MissingRequiredFieldError(f"Expected {context}.products entry to be an object")
    ref = _required_value(product_ref, "__ref", f"{context}.products")
    if not isinstance(ref, str):
        raise MissingRequiredFieldError(f"Expected {context}.products.__ref to be a Product reference")
    return _id_from_ref(ref)


def _reject_duplicate_product_ids(product_ids: tuple[str, ...], context: str) -> None:
    seen: set[str] = set()
    for product_id in product_ids:
        identifier = f"Product:{product_id}"
        if identifier in seen:
            raise AmbiguousCacheEntryError(f"Duplicate {identifier} entry in {context}.products")
        seen.add(identifier)


def _id_from_ref(ref: str) -> str:
    parts = ref.split(":")
    if len(parts) < 2:
        return ref
    return parts[1]


def _master_image_url(concept: dict[str, Any]) -> str | None:
    media_items = concept.get("media") or concept.get("personalizedMeta", {}).get("media") or []
    for media in media_items:
        if media.get("role") == "MASTER" and media.get("url"):
            return str(media["url"])
    for media in media_items:
        if media.get("url"):
            return str(media["url"])
    return None


def _price_info(raw_price: dict[str, Any] | None) -> PriceInfo | None:
    if not raw_price:
        return None
    return PriceInfo(
        base_price=raw_price.get("basePrice"),
        discounted_price=raw_price.get("discountedPrice"),
        discount_text=raw_price.get("discountText"),
        is_free=bool(raw_price.get("isFree")),
        is_exclusive=bool(raw_price.get("isExclusive")),
        is_tied_to_subscription=bool(raw_price.get("isTiedToSubscription")),
        service_branding=_service_branding(raw_price),
        upsell_text=raw_price.get("upsellText"),
    )


def _service_branding(raw_price: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for field in ("serviceBranding", "upsellServiceBranding"):
        for value in raw_price.get(field) or ():
            text = str(value)
            if text not in values:
                values.append(text)
    return tuple(values)


def _required_mapping(mapping: dict[str, Any], key: str, context: str) -> dict[str, Any]:
    value = _required_value(mapping, key, context)
    if not isinstance(value, dict):
        raise MissingRequiredFieldError(f"Expected {context}.{key} to be an object")
    return value


def _required_int(mapping: dict[str, Any], key: str, context: str) -> int:
    return int(_required_value(mapping, key, context))


def _required_list(mapping: dict[str, Any], key: str, context: str) -> list[Any]:
    value = _required_value(mapping, key, context)
    if not isinstance(value, list):
        raise MissingRequiredFieldError(f"Expected {context}.{key} to be a list")
    return value


def _required_value(mapping: dict[str, Any], key: str, context: str) -> Any:
    if key not in mapping or mapping[key] is None:
        raise MissingRequiredFieldError(f"Missing required {context}.{key}")
    return mapping[key]
