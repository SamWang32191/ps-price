from __future__ import annotations

import argparse
from pathlib import Path

from ps_price_crawler.catalog import parse_catalog_page
from ps_price_crawler.client import PlayStationStoreClient, save_fixture
from ps_price_crawler.product import parse_product_detail


def main() -> None:
    parser = argparse.ArgumentParser(prog="ps-price-crawler")
    subcommands = parser.add_subparsers(dest="command", required=True)

    catalog_parser = subcommands.add_parser("catalog")
    catalog_parser.add_argument("--pages", type=int, default=1)
    catalog_parser.add_argument("--save-fixtures", type=Path)

    concept_parser = subcommands.add_parser("concept")
    concept_parser.add_argument("concept_id")
    concept_parser.add_argument("--save-fixtures", type=Path)

    args = parser.parse_args()

    if args.command == "catalog":
        run_catalog(args.pages, args.save_fixtures)
        return
    if args.command == "concept":
        run_concept(args.concept_id, args.save_fixtures)
        return
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
