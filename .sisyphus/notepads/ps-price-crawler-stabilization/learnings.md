# Learnings: ps-price-crawler-stabilization

## 2026-05-15 Session Start
- Active plan: `.sisyphus/plans/ps-price-crawler-stabilization.md`.
- Work is in-place in current repo because `/start-work` omitted `--worktree`.
- Current git status at start showed `.sisyphus/` untracked only.
- Plan scope: crawler contract stabilization only; no Django, DB, scheduler, UI, Docker Compose, auth, notifications, or full catalog detail backfill.

## 2026-05-15 Context Gathering
- Local repo pattern: `pyproject.toml` already has src layout, `ps-price-crawler` script, pytest config (`testpaths`, `pythonpath`, `addopts`).
- README still uses old `python -m venv`, `pip install -e ".[dev]"`, and bare `pytest`; Task 1 should replace with `uv` commands.
- CLI is currently argparse with only `catalog` and `concept`, text-only print output.
- `models.py` is raw data only; normalized price contract should be a separate module, not stuffed into raw dataclasses.
- Existing tests prefer simple helper builders, direct `assert`, and explicit `try/except ValueError`; new tests should match this direct style.
- Official uv CI docs: use `astral-sh/setup-uv`, cache based on `pyproject.toml`/`uv.lock`, `uv sync --locked --extra dev`, then `uv run pytest -v`.
- Caveat: `--extra dev` is correct for current `[project.optional-dependencies].dev`; dependency groups would be different, but this repo uses optional dependency extras.

## 2026-05-15 Task 1
- `uv lock`, `uv sync --extra dev`, and `uv run pytest -v` work from repo root; pytest evidence recorded `47 passed` in `.sisyphus/evidence/task-1-uv-pytest.txt`.
- CI baseline uses `astral-sh/setup-uv@v6` with cache dependency globs for `pyproject.toml` and `uv.lock`, then `uv sync --extra dev --locked` and `uv run pytest -v`.

## 2026-05-15 Task 2
- Added standalone normalized price contract module `src/ps_price_crawler/price_contract.py` with `PriceState`, `NormalizedPrice`, and `normalize_price_info`.
- Confirmed `NT$1,690` and `NT$1,990` are normalized to `169000` and `199000` cents via deterministic string cleanup and integer scaling.
- Preserved raw display text in normalized outputs (`base_display`, `discounted_display`) for localization fidelity.
- Confirmed `FREE`, `PAID`, `DISCOUNTED`, `PS_PLUS`, `UNAVAILABLE`, `NOT_PURCHASABLE`, `UNKNOWN` behavior paths through tests.
- Added `raw_missing_reason` propagation for missing raw price input to satisfy missing-price explicit unknown semantics.

## 2026-05-15 Task 3
- Added `ps-price-crawler fixture-targets --pages N --output PATH` as a bounded catalog-only discovery command; it uses `PlayStationStoreClient.fetch_catalog_page` and existing `parse_catalog_page`, and does not fetch concept detail pages.
- Synthetic CLI tests cover complete classification, missing-category exit `2` with JSON nulls, Roblox `223118` free fallback, and skipping isolated unparseable catalog pages without traceback.
- Live catalog pages can intermittently/consistently omit `CategoryGrid` for specific page numbers (observed pages 10, 13, 21, 63); discovery now records skipped-page warnings and continues scanning bounded pages.
- Live scan found concrete catalog candidates for `free` (`10012874`), `paid_full_price` (`10014149`), `discounted_paid` (`231761`), and `missing_or_unavailable_candidate` (`10002289`) in `.sisyphus/evidence/task-3-fixture-targets.json`.
- Task 3 blocker root cause was a parser mapping gap: raw catalog price payloads expose `upsellServiceBranding: ["PS_PLUS"]`, but `catalog._price_info()` originally preserved only `serviceBranding`.
- Merging `serviceBranding` and `upsellServiceBranding` into `PriceInfo.service_branding` lets the existing `PriceState.PS_PLUS` normalization classify catalog-only PS Plus candidates without concept detail fetches.
- Resolved live discovery found all five required keys; `ps_plus_candidate` came from catalog page 1 concept `10014149` (`《NBA 2K26》`) with merged service branding `['NONE', 'PS_PLUS']`.

## 2026-05-15 Task 4
- Created deterministic committed fixtures under `tests/fixtures/ps_store/` for all five Task 3 targets: free `10012874`, paid `10002075`, discounted `231761`, PS Plus `10014149`, and missing/unknown `10014992`.
- Raw HTML for all five concept detail pages was small enough to commit (`<= 2 MiB` each; total fixture directory `2,786,699` bytes), while duplicate live captures remain under ignored `tests/fixtures/live/`.
- Fixture JSON uses catalog-derived `normalized_state`/`catalog_price_fields` as the target state contract and stores concept-detail parse output separately.
- Existing product parser can fully parse the free target via `DOWNLOAD` CTA inference, but paid/discounted/PS Plus detail pages currently expose CTA data without Product.price, so those JSON fixtures preserve explicit parser errors instead of inventing price fields.

## 2026-05-15 Task 6
- Added pure source strategy policy in `src/ps_price_crawler/source_strategy.py`: `FREE`, `PAID`, and `DISCOUNTED` catalog prices with product IDs use catalog as the snapshot source.
- Detail fallback reason codes are explicit for Task 7 JSON reuse: missing product IDs, `UNKNOWN`/`PS_PLUS`/`UNAVAILABLE`/`NOT_PURCHASABLE` states, and applicable missing future metadata fields.
- Current raw `CatalogItem` does not carry `publisher_name`, `release_date`, or `top_category`; Task 6 treats those future metadata checks as applicable only when an enriched catalog object exposes the fields.

## 2026-05-15 Task 5
- Parser failures now use `CrawlerParseError` subclasses rooted in `ValueError`, preserving existing broad `ValueError` catches while enabling typed assertions for embedded-state, required-field, and ambiguous-cache failures.
- `catalog.normalize_catalog_item_price()` and `product.normalize_product_detail_price()` keep normalized price states outside raw dataclasses while letting parser outputs feed `price_contract.py` directly.
- `parse_product_detail(..., catalog_price=...)` intentionally uses catalog price evidence only when detail `Product.price`/`Concept.price` is absent; empty detail price objects still raise `MissingRequiredFieldError` instead of falling through and pretending the data is fine.
- Deterministic fixture HTML now verifies exact normalized states with catalog evidence, so paid/discounted/PS Plus detail pages missing `Product.price` are handled without fake prices.

## 2026-05-15 Task 7
- Added `--format text|json` to `catalog` and `concept`; text output keeps the existing line-oriented shape, while JSON output serializes normalized price objects, concept/product IDs, source strategy metadata, and typed parser error objects.
- Catalog JSON can include failed page parser errors without aborting the whole report, keeping `pages` authoritative and `items` as the flattened successfully parsed catalog items.
- Concept JSON has no catalog item context by design, so it reports a `concept_detail` source payload with a `no_catalog_item_context` limitation instead of inventing catalog strategy evidence.
- `fixture-report` reads committed `tests/fixtures/ps_store/*.json` offline, reuses committed HTML when present, and writes state coverage plus product IDs, source strategy decisions, normalized prices, current parser errors, and preserved fixture parser errors.
- Task 7 evidence showed committed fixture coverage states `DISCOUNTED`, `FREE`, `PAID`, `PS_PLUS`, and `UNKNOWN` in `.sisyphus/evidence/task-7-fixture-report.json`.
