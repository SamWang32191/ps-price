from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PriceInfo:
    base_price: str | None
    discounted_price: str | None
    discount_text: str | None
    is_free: bool
    is_exclusive: bool
    is_tied_to_subscription: bool
    service_branding: tuple[str, ...] = field(default_factory=tuple)
    upsell_text: str | None = None


@dataclass(frozen=True)
class CatalogItem:
    concept_id: str
    name: str
    product_ids: tuple[str, ...]
    image_url: str | None
    price: PriceInfo | None


@dataclass(frozen=True)
class CatalogPage:
    source_url: str
    category_id: str
    total_count: int
    offset: int
    size: int
    is_last: bool
    items: tuple[CatalogItem, ...]


@dataclass(frozen=True)
class ProductDetail:
    concept_id: str
    concept_name: str
    product_id: str | None
    product_name: str | None
    publisher_name: str | None
    release_date: str | None
    platforms: tuple[str, ...]
    top_category: str | None
    price: PriceInfo | None
