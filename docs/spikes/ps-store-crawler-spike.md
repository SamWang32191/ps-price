# PS Store Crawler Spike

Date: 2026-04-27

## Status

The spike has been closed into a crawler contract stabilization handoff. The repo now has deterministic fixtures, normalized price states, typed parser errors, CLI JSON output, fixture reporting, source strategy policy, and offline CI. The next milestone is Django data foundation only after `uv run pytest -v` verifies this crawler contract.

This is still a non-public PlayStation Store SSR source. The parser reads embedded `__NEXT_DATA__` and `env:*` JSON script payloads. Source drift remains an external maintenance risk, not a mystery gap in the local parser. If the site moves the furniture again, the fixtures should trip loudly instead of letting Django ingest confetti.

## URLs Tested

- `https://store.playstation.com/zh-hant-tw/category/28c9c2b2-cecc-415c-9a08-482a605cb104/1`
- `https://store.playstation.com/zh-hant-tw/category/28c9c2b2-cecc-415c-9a08-482a605cb104/2`
- `https://store.playstation.com/zh-hant-tw/concept/223118`

## Evidence Confirmed

- Catalog SSR pages expose `__NEXT_DATA__`.
- Category grid data appears under `apolloState` keys starting with `CategoryGrid:`.
- Catalog pages include `pageInfo.totalCount`, `pageInfo.offset`, `pageInfo.size`, `pageInfo.isLast`.
- Catalog pages include concept refs, concept names, product IDs when available, image URLs, and price payloads.
- Concept detail pages expose `env:*` JSON scripts with MFE cache data.
- Product detail cache can include product IDs, names, platforms, publisher, release date, and `topCategory` for sampled products.
- Typed parser errors now preserve failure class and message instead of collapsing source problems into generic `ValueError` soup. Soup is for ramen, not ingestion contracts.

## Spike Result

- Catalog page 1 parsed successfully with `total=7990`, `offset=0`, `size=24`, `items=24`, `is_last=False` during the original spike.
- Catalog page 2 parsed successfully with `total=7990`, `offset=24`, `size=24`, `items=24`, `is_last=False` during the original spike.
- Sample catalog concepts parsed successfully:
  - `10002075`, `PRAGMATA`, `NT$1,690`
  - `10005275`, `崩壞：星穹鐵道`, `免費`
  - `223118`, `Roblox`, `免費`
  - `10005069`, `《沙羅週期》`, `NT$1,990`
- Concept `223118` parsed successfully as product `UP1821-PPSA10990_00-1887411884729257`, name `Roblox (簡體中文, 韓文, 英文, 泰文, 繁體中文, 日文)`, platform `PS5`, category `GAME`, price `免費`.
- Live catalog state is currently exposed at `props.apolloState`; the original fixture shape `props.pageProps.apolloState` is still supported by tests.
- Live Roblox concept detail does not expose a direct product `price` object for the default product; the parser infers `免費` only when a `DOWNLOAD` CTA is present.

## Stabilized Contract Artifacts

- `src/ps_price_crawler/price_contract.py` defines `PriceState` values: `FREE`, `PAID`, `DISCOUNTED`, `PS_PLUS`, `UNAVAILABLE`, `NOT_PURCHASABLE`, `UNKNOWN`.
- `NormalizedPrice` preserves normalized amounts and raw display evidence: `currency`, `base_amount_cents`, `discounted_amount_cents`, `plus_amount_cents`, `base_display`, `discounted_display`, `discount_text`, `service_branding`, `upsell_text`, `source`, and `raw_missing_reason`.
- Catalog and product parser helpers return normalized prices without mutating the raw dataclasses.
- Parser failures use typed error classes for missing embedded state, missing required fields, and ambiguous cache entries.
- CLI JSON reports include normalized price payloads, source strategy metadata, and parser error objects.
- `fixture-report` summarizes committed fixture coverage offline from `tests/fixtures/ps_store`.

## Fixture Coverage

Deterministic committed fixtures under `tests/fixtures/ps_store/` cover these normalized states:

- `FREE`, concept `10012874`.
- `PAID`, concept `10002075`.
- `DISCOUNTED`, concept `231761`.
- `PS_PLUS`, concept `10014149`.
- `UNKNOWN`, concept `10014992`, used as the deterministic unavailable/not-purchasable risk fallback because the live source exposed missing catalog price/default product behavior rather than a clean public unavailable state.

The fixture contract records catalog price fields separately from concept detail parser output. Paid, discounted, and PS Plus detail pages currently expose CTA/cache data without direct `Product.price`, so the fixture metadata preserves parser errors rather than inventing prices. Good. Fake data is just technical debt wearing a Halloween mask.

Malformed embedded-state cases are covered by parser tests. Live raw captures remain under ignored `tests/fixtures/live/`; committed fixtures are the deterministic offline contract.

## Canonical Commands

Setup and offline verification:

```bash
uv sync --extra dev
uv run pytest -v
```

Manual live smoke and fixture refresh commands:

```bash
uv run ps-price-crawler catalog --pages 2 --format json
uv run ps-price-crawler concept 223118 --format json
uv run ps-price-crawler fixture-targets --pages 80 --output .sisyphus/evidence/task-3-fixture-targets.json
uv run ps-price-crawler fixture-report --fixtures tests/fixtures/ps_store --output .sisyphus/evidence/fixture-report.json
```

`fixture-report` is offline because it reads committed fixtures. `catalog`, `concept`, and `fixture-targets` are live/manual commands and must not be required by CI.

## CI Policy

CI installs dependencies with `uv sync --extra dev --locked` and runs `uv run pytest -v`. CI does not run live PlayStation Store commands, does not refresh fixtures, and does not depend on network source stability. If someone wires live crawler calls into CI, that is not observability, that is a slot machine with YAML syntax.

## Snapshot Source Strategy Decision

Daily price snapshots use a catalog-first, concept-detail fallback policy.

Use catalog as the snapshot source when:

- The normalized catalog state is `FREE`, `PAID`, or `DISCOUNTED`.
- Catalog item product IDs are present.

Fetch concept detail when:

- The normalized catalog state is `UNKNOWN`, `PS_PLUS`, `UNAVAILABLE`, or `NOT_PURCHASABLE`.
- Catalog product IDs are missing.
- Later Django ingestion needs `publisher_name`, `release_date`, or `top_category`, and those fields are missing from the catalog item shape.

Full concept-detail backfill remains out of scope for this milestone. Future sync work should queue targeted detail fetches for fallback cases, not implement a full detail crawl or historical backfill here.

## Next milestone input

The Django data foundation can rely on these fields from the crawler contract:

- Concept ID.
- Product IDs when present.
- Concept and product names.
- Normalized price state.
- Currency, amount cents, and display fields.
- Publisher, release date, and top category from concept detail where parsed.
- Source strategy decision: `source`, `reason`, `reason_codes`, `normalized_state`, `product_ids`, and `missing_metadata_fields`.
- Parser error type and message.

Fields and meanings still treated as source-risk:

- PS Plus effective price semantics.
- Unavailable versus not purchasable distinctions.
- Missing product IDs or missing `defaultProduct`.
- SSR schema drift.
- Localized display text and currency parsing.
- Concept detail price absence.

Map to the later Django data foundation carefully:

- `StoreProduct` can start from concept/product IDs, URL, title/name, platform where parsed, source product type/top category, publisher, visibility flags, and image URL.
- `PriceSnapshot` can start from normalized price state, TWD amount cents, raw display text, discount text, PS Plus amount when signaled, and explicit non-purchasable/unknown states.
- `SyncRun` should record sync type, start/end time, status, success count, failure count, and summary.
- `SyncError` should store source URL or concept/product ID plus parser error type/message and retry outcome.

Do not start Django until the crawler contract has fresh offline verification evidence. A schema built on unverified crawler output is just a spreadsheet with a superiority complex.
