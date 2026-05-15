from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ps_price_crawler.catalog import normalize_catalog_item_price, parse_catalog_page
from ps_price_crawler.client import PlayStationStoreClient, concept_url, save_fixture
from ps_price_crawler.models import CatalogItem, PriceInfo, ProductDetail
from ps_price_crawler.price_contract import NormalizedPrice, PriceState, normalize_price_info
from ps_price_crawler.product import normalize_product_detail_price, parse_product_detail
from ps_price_crawler.source_strategy import SnapshotSourceDecision, choose_snapshot_source


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
    catalog_parser.add_argument("--format", choices=("text", "json"), default="text")

    concept_parser = subcommands.add_parser("concept")
    concept_parser.add_argument("concept_id")
    concept_parser.add_argument("--save-fixtures", type=Path)
    concept_parser.add_argument("--format", choices=("text", "json"), default="text")

    fixture_targets_parser = subcommands.add_parser("fixture-targets")
    fixture_targets_parser.add_argument("--pages", type=int, default=80)
    fixture_targets_parser.add_argument("--output", type=Path, required=True)

    fixture_report_parser = subcommands.add_parser("fixture-report")
    fixture_report_parser.add_argument("--fixtures", type=Path, required=True)
    fixture_report_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()

    if args.command == "catalog":
        code = run_catalog(args.pages, args.save_fixtures, args.format)
        if code:
            raise SystemExit(code)
        return
    if args.command == "concept":
        code = run_concept(args.concept_id, args.save_fixtures, args.format)
        if code:
            raise SystemExit(code)
        return
    if args.command == "fixture-targets":
        raise SystemExit(run_fixture_targets(args.pages, args.output))
    if args.command == "fixture-report":
        code = run_fixture_report(args.fixtures, args.output)
        if code:
            raise SystemExit(code)
        return
    raise SystemExit(f"Unsupported command: {args.command}")


def run_catalog(pages: int, fixture_dir: Path | None, output_format: str = "text") -> int:
    if output_format == "json":
        return _run_catalog_json(pages, fixture_dir)

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
    return 0


def run_concept(concept_id: str, fixture_dir: Path | None, output_format: str = "text") -> int:
    if output_format == "json":
        return _run_concept_json(concept_id, fixture_dir)

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
    return 0


def _run_catalog_json(pages: int, fixture_dir: Path | None) -> int:
    payload: dict[str, Any] = {"pages": [], "items": []}
    errors: list[dict[str, Any]] = []

    with PlayStationStoreClient() as client:
        for page_number in range(1, pages + 1):
            url, html = client.fetch_catalog_page(page_number)
            if fixture_dir is not None:
                save_fixture(fixture_dir, f"catalog_page_{page_number}.html", html)
            try:
                parsed = parse_catalog_page(html, source_url=url)
            except Exception as exc:
                error = _parser_error(exc)
                errors.append({"page_number": page_number, "source_url": url, **error})
                payload["pages"].append(_catalog_page_error_payload(page_number, url, error))
                continue

            item_payloads = [_catalog_item_payload(item) for item in parsed.items]
            payload["pages"].append(_catalog_page_payload(page_number, parsed, item_payloads))
            payload["items"].extend(item_payloads)

    payload["errors"] = errors
    _print_json(payload)
    return 0


def _run_concept_json(concept_id: str, fixture_dir: Path | None) -> int:
    with PlayStationStoreClient() as client:
        url, html = client.fetch_concept(concept_id)
    if fixture_dir is not None:
        save_fixture(fixture_dir, f"concept_{concept_id}.html", html)

    try:
        detail = parse_product_detail(html, concept_id=concept_id)
    except Exception as exc:
        _print_json(_concept_error_payload(concept_id, url, exc))
        return 1

    _print_json(_product_detail_payload(detail, source_url=url))
    return 0


def run_fixture_report(fixtures_dir: Path, output_path: Path) -> int:
    fixtures = [
        _fixture_report_item(fixtures_dir, path)
        for path in sorted(fixtures_dir.glob("concept_*.json"))
    ]
    payload = {
        "fixtures_dir": str(fixtures_dir),
        "coverage": _fixture_coverage(fixtures),
        "fixtures": fixtures,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    states = ",".join(payload["coverage"]["states_present"])
    print(f"fixture-report complete output={output_path} fixtures={len(fixtures)} states={states}")
    return 0


def _catalog_page_payload(
    page_number: int,
    parsed: Any,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "page_number": page_number,
        "source_url": parsed.source_url,
        "category_id": parsed.category_id,
        "total_count": parsed.total_count,
        "offset": parsed.offset,
        "size": parsed.size,
        "is_last": parsed.is_last,
        "items": items,
        "parser_error": None,
    }


def _catalog_page_error_payload(page_number: int, source_url: str, error: dict[str, str]) -> dict[str, Any]:
    return {
        "page_number": page_number,
        "source_url": source_url,
        "category_id": None,
        "total_count": None,
        "offset": None,
        "size": None,
        "is_last": None,
        "items": [],
        "parser_error": error,
    }


def _catalog_item_payload(item: CatalogItem) -> dict[str, Any]:
    normalized = normalize_catalog_item_price(item)
    decision = choose_snapshot_source(item, normalized)
    return {
        "concept_id": item.concept_id,
        "name": item.name,
        "product_ids": list(item.product_ids),
        "image_url": item.image_url,
        "price": _normalized_price_payload(normalized),
        "source_strategy": _source_decision_payload(decision),
        "parser_error": None,
    }


def _product_detail_payload(detail: ProductDetail, *, source_url: str) -> dict[str, Any]:
    normalized = normalize_product_detail_price(detail)
    return {
        "concept_id": detail.concept_id,
        "concept_name": detail.concept_name,
        "product_id": detail.product_id,
        "product_ids": [detail.product_id] if detail.product_id else [],
        "product_name": detail.product_name,
        "publisher_name": detail.publisher_name,
        "release_date": detail.release_date,
        "platforms": list(detail.platforms),
        "top_category": detail.top_category,
        "source_url": source_url,
        "price": _normalized_price_payload(normalized),
        "source_strategy": _concept_detail_source_payload(),
        "parser_error": None,
    }


def _concept_error_payload(concept_id: str, source_url: str, exc: Exception) -> dict[str, Any]:
    return {
        "concept_id": concept_id,
        "concept_name": None,
        "product_id": None,
        "product_ids": [],
        "product_name": None,
        "publisher_name": None,
        "release_date": None,
        "platforms": [],
        "top_category": None,
        "source_url": source_url,
        "price": None,
        "source_strategy": _concept_detail_source_payload(parser_error=True),
        "parser_error": _parser_error(exc),
    }


def _fixture_report_item(fixtures_dir: Path, json_path: Path) -> dict[str, Any]:
    fixture = json.loads(json_path.read_text(encoding="utf-8"))
    catalog_price = _catalog_price_from_fixture(fixture)
    normalized = normalize_price_info(
        catalog_price,
        source="catalog",
        raw_missing_reason="Catalog item price block missing" if catalog_price is None else None,
    )
    detail = _parse_fixture_detail(fixtures_dir, fixture, catalog_price)
    product_ids = _fixture_product_ids(fixture, detail)
    parser_error = detail["parser_error"]
    item = CatalogItem(
        concept_id=str(fixture["concept_id"]),
        name=str(fixture["name"]),
        product_ids=tuple(product_ids),
        image_url=None,
        price=catalog_price,
    )
    decision = choose_snapshot_source(item, normalized)

    return {
        "file": json_path.name,
        "target_key": fixture["target_key"],
        "concept_id": str(fixture["concept_id"]),
        "name": fixture["name"],
        "source_url": fixture["source_url"],
        "catalog_source_url": fixture.get("catalog_source_url"),
        "product_id": product_ids[0] if product_ids else None,
        "product_ids": product_ids,
        "state": normalized.state.value,
        "price": _normalized_price_payload(normalized),
        "source_strategy": _source_decision_payload(decision),
        "parser_error": parser_error,
        "fixture_parser_error": fixture.get("parser_error"),
        "raw_html": {
            "committed": fixture.get("raw_html_committed"),
            "fixture": fixture.get("raw_html_fixture"),
            "sha256": fixture.get("raw_html_sha256"),
            "size_bytes": fixture.get("raw_html_size_bytes"),
            "omitted_reason": fixture.get("raw_html_omitted_reason"),
        },
    }


def _parse_fixture_detail(
    fixtures_dir: Path,
    fixture: dict[str, Any],
    catalog_price: PriceInfo | None,
) -> dict[str, Any]:
    raw_html_fixture = fixture.get("raw_html_fixture")
    if not fixture.get("raw_html_committed") or not raw_html_fixture:
        return {"detail": None, "parser_error": fixture.get("parser_error")}

    html = (fixtures_dir / str(raw_html_fixture)).read_text(encoding="utf-8")
    try:
        detail = parse_product_detail(
            html,
            concept_id=str(fixture["concept_id"]),
            catalog_price=catalog_price,
        )
    except Exception as exc:
        return {"detail": None, "parser_error": _parser_error(exc)}
    return {"detail": detail, "parser_error": None}


def _fixture_product_ids(fixture: dict[str, Any], detail_result: dict[str, Any]) -> list[str]:
    detail = detail_result["detail"]
    if isinstance(detail, ProductDetail) and detail.product_id:
        return [detail.product_id]

    product_detail = fixture.get("product_detail")
    if isinstance(product_detail, dict) and product_detail.get("product_id"):
        return [str(product_detail["product_id"])]

    return []


def _fixture_coverage(fixtures: list[dict[str, Any]]) -> dict[str, Any]:
    states_present = sorted({fixture["state"] for fixture in fixtures})
    required_clear_states = {"FREE", "PAID", "DISCOUNTED", "PS_PLUS"}
    ambiguous_states = {"UNAVAILABLE", "NOT_PURCHASABLE", "UNKNOWN"}
    return {
        "states_present": states_present,
        "required_clear_states": sorted(required_clear_states),
        "ambiguous_state_options": sorted(ambiguous_states),
        "missing_required_clear_states": sorted(required_clear_states - set(states_present)),
        "has_ambiguous_or_unavailable_state": bool(ambiguous_states & set(states_present)),
        "has_required_coverage": required_clear_states <= set(states_present)
        and bool(ambiguous_states & set(states_present)),
    }


def _catalog_price_from_fixture(fixture: dict[str, Any]) -> PriceInfo | None:
    fields = fixture["catalog_price_fields"]
    if fields["basePrice"] is None and fields["discountedPrice"] is None:
        return None
    return PriceInfo(
        base_price=fields["basePrice"],
        discounted_price=fields["discountedPrice"],
        discount_text=fields.get("discountText"),
        is_free=bool(fields.get("isFree")),
        is_exclusive=bool(fields.get("isExclusive")),
        is_tied_to_subscription=bool(fields.get("isTiedToSubscription")),
        service_branding=tuple(fields.get("serviceBranding") or ()),
        upsell_text=fields.get("upsellText"),
    )


def _normalized_price_payload(price: NormalizedPrice) -> dict[str, Any]:
    return {
        "state": price.state.value,
        "currency": price.currency,
        "base_amount_cents": price.base_amount_cents,
        "discounted_amount_cents": price.discounted_amount_cents,
        "plus_amount_cents": price.plus_amount_cents,
        "base_display": price.base_display,
        "discounted_display": price.discounted_display,
        "discount_text": price.discount_text,
        "service_branding": list(price.service_branding),
        "upsell_text": price.upsell_text,
        "source": price.source,
        "raw_missing_reason": price.raw_missing_reason,
    }


def _source_decision_payload(decision: SnapshotSourceDecision) -> dict[str, Any]:
    return {
        "source": decision.source,
        "reason": decision.reason,
        "reason_codes": list(decision.reason_codes),
        "normalized_state": decision.normalized_state.value,
        "product_ids": list(decision.product_ids),
        "missing_metadata_fields": list(decision.missing_metadata_fields),
    }


def _concept_detail_source_payload(*, parser_error: bool = False) -> dict[str, Any]:
    reason_codes = ["no_catalog_item_context"]
    if parser_error:
        reason_codes.append("parser_error")
    return {
        "source": "concept_detail",
        "reason": "parser_error" if parser_error else "concept_detail_command",
        "reason_codes": reason_codes,
        "limitations": [
            "catalog item context is unavailable; catalog strategy evidence cannot be computed from concept-only command"
        ],
    }


def _parser_error(exc: Exception) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False))


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
