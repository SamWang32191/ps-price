from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ps_price_crawler.catalog import parse_catalog_page
from ps_price_crawler.client import PlayStationStoreClient, concept_url, save_fixture
from ps_price_crawler.models import CatalogItem, PriceInfo
from ps_price_crawler.price_contract import PriceState, normalize_price_info
from ps_price_crawler.product import parse_product_detail


REQUIRED_FIXTURE_TARGET_KEYS = (
    "free",
    "paid_full_price",
    "discounted_paid",
    "ps_plus_candidate",
    "missing_or_unavailable_candidate",
)
FREE_FALLBACK_CONCEPT_ID = "223118"


def main() -> None:
    parser = argparse.ArgumentParser(prog="ps-price-crawler")
    subcommands = parser.add_subparsers(dest="command", required=True)

    catalog_parser = subcommands.add_parser("catalog")
    catalog_parser.add_argument("--pages", type=int, default=1)
    catalog_parser.add_argument("--save-fixtures", type=Path)

    concept_parser = subcommands.add_parser("concept")
    concept_parser.add_argument("concept_id")
    concept_parser.add_argument("--save-fixtures", type=Path)

    fixture_targets_parser = subcommands.add_parser("fixture-targets")
    fixture_targets_parser.add_argument("--pages", type=int, default=80)
    fixture_targets_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()

    if args.command == "catalog":
        run_catalog(args.pages, args.save_fixtures)
        return
    if args.command == "concept":
        run_concept(args.concept_id, args.save_fixtures)
        return
    if args.command == "fixture-targets":
        raise SystemExit(run_fixture_targets(args.pages, args.output))
    raise SystemExit(f"Unsupported command: {args.command}")


def run_catalog(pages: int, fixture_dir: Path | None) -> None:
    with PlayStationStoreClient() as client:
        for page_number in range(1, pages + 1):
            url, html = client.fetch_catalog_page(page_number)
            parsed = parse_catalog_page(html, source_url=url)
            if fixture_dir is not None:
                save_fixture(fixture_dir, f"catalog_page_{page_number}.html", html)
            print(
                f"catalog page={page_number} total={parsed.total_count} "
                f"offset={parsed.offset} size={parsed.size} items={len(parsed.items)} "
                f"is_last={parsed.is_last}"
            )
            for item in parsed.items[:5]:
                price = item.price.discounted_price if item.price else "NO_PRICE"
                print(f"  concept={item.concept_id} name={item.name} price={price}")


def run_concept(concept_id: str, fixture_dir: Path | None) -> None:
    with PlayStationStoreClient() as client:
        url, html = client.fetch_concept(concept_id)
    detail = parse_product_detail(html, concept_id=concept_id)
    if fixture_dir is not None:
        save_fixture(fixture_dir, f"concept_{concept_id}.html", html)
    price = detail.price.discounted_price if detail.price else "NO_PRICE"
    print(
        f"concept={detail.concept_id} product={detail.product_id} "
        f"name={detail.product_name or detail.concept_name} "
        f"platforms={','.join(detail.platforms)} category={detail.top_category} price={price}"
    )


def run_fixture_targets(pages: int, output_path: Path) -> int:
    targets: dict[str, dict[str, Any] | None] = {key: None for key in REQUIRED_FIXTURE_TARGET_KEYS}

    with PlayStationStoreClient() as client:
        for page_number in range(1, pages + 1):
            try:
                url, html = client.fetch_catalog_page(page_number)
                parsed = parse_catalog_page(html, source_url=url)
            except Exception as exc:
                print(f"fixture-targets skipped page={page_number} error={type(exc).__name__}: {exc}")
                continue
            for item in parsed.items:
                _record_fixture_target(targets, item, parsed.source_url)
            if all(targets[key] is not None for key in REQUIRED_FIXTURE_TARGET_KEYS):
                break

    if targets["free"] is None:
        targets["free"] = _free_fallback_target()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(targets, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    missing_keys = [key for key, value in targets.items() if value is None]
    if missing_keys:
        print(f"fixture-targets incomplete missing={','.join(missing_keys)} output={output_path}")
        return 2

    print(f"fixture-targets complete output={output_path}")
    return 0


def _record_fixture_target(
    targets: dict[str, dict[str, Any] | None], item: CatalogItem, source_url: str
) -> None:
    normalized = normalize_price_info(
        item.price,
        source="catalog",
        raw_missing_reason="Catalog item price block missing" if item.price is None else None,
    )

    if normalized.state == PriceState.FREE:
        _set_target_once(targets, "free", item, source_url, "catalog price normalized as FREE")
        return

    if normalized.state == PriceState.PAID:
        _set_target_once(targets, "paid_full_price", item, source_url, "catalog price normalized as PAID")
        return

    if normalized.state == PriceState.DISCOUNTED:
        _set_target_once(targets, "discounted_paid", item, source_url, "catalog price normalized as DISCOUNTED")
        return

    if normalized.state == PriceState.PS_PLUS:
        _set_target_once(targets, "ps_plus_candidate", item, source_url, "catalog price normalized as PS_PLUS")
        return

    if normalized.state in {PriceState.UNAVAILABLE, PriceState.NOT_PURCHASABLE, PriceState.UNKNOWN}:
        _set_target_once(
            targets,
            "missing_or_unavailable_candidate",
            item,
            source_url,
            f"catalog price normalized as {normalized.state.value}",
        )


def _set_target_once(
    targets: dict[str, dict[str, Any] | None],
    key: str,
    item: CatalogItem,
    source_url: str,
    reason: str,
) -> None:
    if targets[key] is not None:
        return
    targets[key] = _target_payload(item, source_url, reason)


def _target_payload(item: CatalogItem, source_url: str, reason: str) -> dict[str, Any]:
    return {
        "concept_id": item.concept_id,
        "name": item.name,
        "source_url": source_url,
        "price_fields": _price_fields(item.price),
        "reason": reason,
    }


def _free_fallback_target() -> dict[str, Any]:
    return {
        "concept_id": FREE_FALLBACK_CONCEPT_ID,
        "name": "Roblox",
        "source_url": concept_url(FREE_FALLBACK_CONCEPT_ID),
        "price_fields": {
            "basePrice": "免費",
            "discountedPrice": "免費",
            "discountText": None,
            "isFree": True,
            "isExclusive": False,
            "isTiedToSubscription": False,
            "serviceBranding": ["NONE"],
            "upsellText": None,
            "normalizedState": PriceState.FREE.value,
        },
        "reason": "known free fallback used after catalog scan found no free item",
    }


def _price_fields(price: PriceInfo | None) -> dict[str, Any]:
    normalized = normalize_price_info(
        price,
        source="catalog",
        raw_missing_reason="Catalog item price block missing" if price is None else None,
    )
    if price is None:
        return {
            "basePrice": None,
            "discountedPrice": None,
            "discountText": None,
            "isFree": None,
            "isExclusive": None,
            "isTiedToSubscription": None,
            "serviceBranding": [],
            "upsellText": None,
            "normalizedState": normalized.state.value,
            "rawMissingReason": normalized.raw_missing_reason,
        }

    return {
        "basePrice": price.base_price,
        "discountedPrice": price.discounted_price,
        "discountText": price.discount_text,
        "isFree": price.is_free,
        "isExclusive": price.is_exclusive,
        "isTiedToSubscription": price.is_tied_to_subscription,
        "serviceBranding": list(price.service_branding),
        "upsellText": price.upsell_text,
        "normalizedState": normalized.state.value,
    }
