from datetime import date

import pytest
from ps_price_crawler.models import CatalogItem, CatalogPage
from ps_price_crawler.price_contract import NormalizedPrice, PriceState
from ps_price_crawler.source_strategy import SnapshotSourceDecision
from ps_price_sync.models import SyncRun
from ps_price_sync.services import sync_runner


@pytest.mark.django_db
def test_run_snapshot_sync_uses_concept_url_for_catalog_path_and_does_not_count_noop_snapshot(monkeypatch):
    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def fetch_catalog_page(self, page: int):
            del page
            return "https://store.playstation.com/zh-hant-tw/category/test/1", "catalog-page-html"

    def fake_parse_catalog_page(html: str, source_url: str) -> CatalogPage:
        del html, source_url
        return CatalogPage(
            source_url="https://store.playstation.com/zh-hant-tw/category/test/1",
            category_id="test",
            total_count=1,
            offset=0,
            size=24,
            is_last=True,
            items=(
                CatalogItem(
                    concept_id="223118",
                    name="Game 223118",
                    product_ids=("UP1821-PPSA10990_00-1887411884729257",),
                    image_url="https://example.test/image.jpg",
                    price=None,
                ),
            ),
        )

    def fake_normalize_catalog_item_price(item: CatalogItem) -> NormalizedPrice:
        del item
        return NormalizedPrice(
            state=PriceState.PAID,
            currency="TWD",
            base_amount_cents=169000,
            discounted_amount_cents=139000,
            plus_amount_cents=None,
            base_display="NT$1,690",
            discounted_display="NT$1,390",
            discount_text="",
            service_branding=(),
            upsell_text=None,
            source="catalog",
            raw_missing_reason=None,
        )

    def fake_choose_snapshot_source(item: CatalogItem, normalized_price: NormalizedPrice) -> SnapshotSourceDecision:
        del item, normalized_price
        return SnapshotSourceDecision(
            source="catalog",
            reason="catalog_price_snapshot",
            reason_codes=("clear_catalog_price", "product_ids_present"),
            normalized_state=PriceState.PAID,
            product_ids=("UP1821-PPSA10990_00-1887411884729257",),
            missing_metadata_fields=(),
        )

    captured: dict[str, str] = {}

    def fake_ingest_catalog_snapshot(
        *,
        sync_run: SyncRun,
        item,
        normalized_price,
        decision,
        snapshot_date,
        source_url: str,
    ) -> None:
        del sync_run, item, normalized_price, decision, snapshot_date
        captured["source_url"] = source_url
        return None

    sync_run = SyncRun.objects.create(sync_type="snapshot_only", status="running")

    monkeypatch.setattr(sync_runner, "PlayStationStoreClient", lambda: FakeClient())
    monkeypatch.setattr(sync_runner, "parse_catalog_page", fake_parse_catalog_page)
    monkeypatch.setattr(sync_runner, "normalize_catalog_item_price", fake_normalize_catalog_item_price)
    monkeypatch.setattr(sync_runner, "choose_snapshot_source", fake_choose_snapshot_source)
    monkeypatch.setattr(sync_runner, "ingest_catalog_snapshot", fake_ingest_catalog_snapshot)

    sync_runner.run_snapshot_sync(
        sync_run=sync_run,
        page_limit=1,
        snapshot_date=date(2026, 5, 16),
    )

    assert captured["source_url"] == "https://store.playstation.com/zh-hant-tw/concept/223118"
    sync_run.refresh_from_db()
    assert sync_run.success_count == 0
