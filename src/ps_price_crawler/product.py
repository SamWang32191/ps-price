from __future__ import annotations

from typing import Any

from ps_price_crawler.catalog import _id_from_ref, _price_info
from ps_price_crawler.models import PriceInfo, ProductDetail
from ps_price_crawler.next_data import extract_embedded_state


def parse_product_detail(html: str, concept_id: str) -> ProductDetail:
    state = extract_embedded_state(html)
    cache = _combined_cache(state.env_scripts)
    concept = _find_concept(cache, concept_id)
    product = _default_product(cache, concept)

    if "releaseDate" in product:
        release_date = product["releaseDate"]
    else:
        release_date = _concept_release_date(concept)
    if not isinstance(release_date, str) or not release_date:
        raise ValueError("Missing required Product.releaseDate")
    if "publisherName" in product:
        publisher_name = product["publisherName"]
    else:
        publisher_name = concept.get("publisherName")
    if not isinstance(publisher_name, str) or not publisher_name:
        raise ValueError("Missing required Product.publisherName")
    if "price" in product:
        raw_price = product["price"]
    elif "price" in concept:
        raw_price = concept["price"]
    else:
        raw_price = None
    price = _price_from_raw_or_download_cta(raw_price, product)
    if price is None:
        raise ValueError("Missing required Product.price")

    return ProductDetail(
        concept_id=_required_str(concept, "id", f"Concept:{concept_id}"),
        concept_name=_required_str(concept, "name", f"Concept:{concept_id}"),
        product_id=_required_str(product, "id", "Product"),
        product_name=_required_str(product, "name", "Product"),
        publisher_name=str(publisher_name),
        release_date=release_date,
        platforms=tuple(_required_non_empty_list(product, "platforms", "Product")),
        top_category=_required_str(product, "topCategory", "Product"),
        price=price,
    )


def _price_from_raw_or_download_cta(raw_price: Any, product: dict[str, Any]) -> PriceInfo | None:
    if isinstance(raw_price, dict) and raw_price:
        return _price_info(raw_price)
    if raw_price is None and _has_download_cta(product):
        return PriceInfo(
            base_price="免費",
            discounted_price="免費",
            discount_text=None,
            is_free=True,
            is_exclusive=False,
            is_tied_to_subscription=False,
        )
    return None


def _has_download_cta(product: dict[str, Any]) -> bool:
    webctas = product.get("webctas")
    if not isinstance(webctas, list):
        return False
    return any(isinstance(cta, dict) and cta.get("type") == "DOWNLOAD" for cta in webctas)


def _combined_cache(env_scripts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    combined: dict[str, Any] = {}
    for payload in env_scripts.values():
        cache = payload.get("cache")
        if isinstance(cache, dict):
            for key, value in cache.items():
                if (
                    key in combined
                    and isinstance(combined[key], dict)
                    and isinstance(value, dict)
                ):
                    combined[key] = {**combined[key], **value}
                else:
                    combined[key] = value
    return combined


def _find_concept(cache: dict[str, Any], concept_id: str) -> dict[str, Any]:
    concept = _find_cache_entry(cache, "Concept", concept_id)
    if concept is not None:
        return concept
    raise ValueError(f"Concept {concept_id} not found in embedded env cache")


def _default_product(cache: dict[str, Any], concept: dict[str, Any]) -> dict[str, Any]:
    default_product = _required_mapping(concept, "defaultProduct", "Concept")
    product_id = _product_id_from_default_ref(default_product)
    product = _find_cache_entry(cache, "Product", product_id)
    if product is not None:
        return product

    raise ValueError(f"Product {product_id} not found in embedded env cache")


def _product_id_from_default_ref(default_product: dict[str, Any]) -> str:
    product_ref = _required_value(default_product, "__ref", "Concept.defaultProduct")
    if not isinstance(product_ref, str):
        raise ValueError("Expected Concept.defaultProduct.__ref to be a Product reference")
    parts = product_ref.split(":")
    if len(parts) != 2 or parts[0] != "Product" or not parts[1]:
        raise ValueError("Expected Concept.defaultProduct.__ref to be a Product reference")
    return _id_from_ref(product_ref)


def _find_cache_entry(cache: dict[str, Any], typename: str, entity_id: str) -> dict[str, Any] | None:
    prefix = f"{typename}:{entity_id}"
    exact_value = cache.get(prefix)
    if isinstance(exact_value, dict):
        return exact_value

    suffix_matches = [
        value
        for key, value in cache.items()
        if key.startswith(f"{prefix}:") and isinstance(value, dict)
    ]
    if len(suffix_matches) == 1:
        return suffix_matches[0]
    if len(suffix_matches) > 1:
        raise ValueError(f"Multiple {typename} cache entries found for {entity_id}")
    return None


def _concept_release_date(concept: dict[str, Any]) -> str | None:
    release_date = concept.get("releaseDate")
    if isinstance(release_date, dict):
        value = release_date.get("value")
        return str(value) if value else None
    if isinstance(release_date, str):
        return release_date
    return None


def _required_mapping(mapping: dict[str, Any], key: str, context: str) -> dict[str, Any]:
    value = _required_value(mapping, key, context)
    if not isinstance(value, dict):
        raise ValueError(f"Expected {context}.{key} to be an object")
    return value


def _required_non_empty_list(mapping: dict[str, Any], key: str, context: str) -> list[Any]:
    value = _required_value(mapping, key, context)
    if not isinstance(value, list) or not value:
        raise ValueError(f"Expected {context}.{key} to be a non-empty list")
    return value


def _required_str(mapping: dict[str, Any], key: str, context: str) -> str:
    value = _required_value(mapping, key, context)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Expected {context}.{key} to be a non-empty string")
    return value


def _required_value(mapping: dict[str, Any], key: str, context: str) -> Any:
    if key not in mapping or mapping[key] is None:
        raise ValueError(f"Missing required {context}.{key}")
    return mapping[key]
