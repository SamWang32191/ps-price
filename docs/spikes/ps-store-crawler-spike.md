# PS Store Crawler Spike

Date: 2026-04-27

## URLs Tested

- `https://store.playstation.com/zh-hant-tw/category/28c9c2b2-cecc-415c-9a08-482a605cb104/1`
- `https://store.playstation.com/zh-hant-tw/category/28c9c2b2-cecc-415c-9a08-482a605cb104/2`
- `https://store.playstation.com/zh-hant-tw/concept/223118`

## Expected Evidence

- Catalog SSR pages expose `__NEXT_DATA__`.
- Category grid data appears under `apolloState` keys starting with `CategoryGrid:`.
- Catalog pages include `pageInfo.totalCount`, `pageInfo.offset`, `pageInfo.size`, `pageInfo.isLast`.
- Catalog pages include concept refs and concept names.
- Concept detail pages expose `env:*` JSON scripts with MFE cache data.
- Product detail cache includes product IDs, names, platforms, publisher, release date, and `topCategory` for at least one sampled product.

## Spike Result

- Catalog page 1 parsed successfully with `total=7990`, `offset=0`, `size=24`, `items=24`, `is_last=False`.
- Catalog page 2 parsed successfully with `total=7990`, `offset=24`, `size=24`, `items=24`, `is_last=False`.
- Sample catalog concepts parsed successfully:
  - `10002075` - `PRAGMATA` - `NT$1,690`
  - `10005275` - `崩壞：星穹鐵道` - `免費`
  - `223118` - `Roblox` - `免費`
  - `10005069` - `《沙羅週期》` - `NT$1,990`
- Concept `223118` parsed successfully as product `UP1821-PPSA10990_00-1887411884729257`, name `Roblox (簡體中文, 韓文, 英文, 泰文, 繁體中文, 日文)`, platform `PS5`, category `GAME`, price `免費`.
- Live catalog state is currently exposed at `props.apolloState`; the original fixture shape `props.pageProps.apolloState` is still supported by tests.
- Live Roblox concept detail does not expose a direct product `price` object for the default product; the parser infers `免費` only when a `DOWNLOAD` CTA is present.

## Known Gaps After Spike

- Confirm a discounted paid product fixture.
- Confirm a PS Plus price fixture.
- Confirm an unavailable or non-purchasable product fixture.

## Snapshot Source Strategy Decision

Daily price snapshots use a **catalog-first, concept-detail fallback** policy. Catalog page prices are sufficient for the daily snapshot when the normalized catalog state is `FREE`, `PAID`, or `DISCOUNTED` and the catalog item includes product IDs. These states are already explicit enough for `PriceSnapshot` values without treating concept detail pages as the source of truth.

Concept detail should be fetched only when the catalog data is ambiguous or incomplete: normalized state `UNKNOWN`, `PS_PLUS`, `UNAVAILABLE`, or `NOT_PURCHASABLE`; missing product IDs; or missing later Django metadata fields such as `publisher_name`, `release_date`, or `top_category` when those fields are part of an enriched catalog handoff. This preserves detail pages for cases where they answer a concrete question instead of turning every sync into a 7,990-item pilgrimage.

Full concept-detail backfill is out of scope for this milestone. Future sync work should queue targeted detail fetches for fallback cases, not implement a full detail crawl or historical backfill here.
