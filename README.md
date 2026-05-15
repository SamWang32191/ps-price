# ps-price

自架的 PlayStation Store 台灣價格追蹤器。

## 目前里程碑

目前 repo 已完成 crawler contract stabilization。這個階段把 PlayStation Store 台灣 SSR 頁面的 spike 收斂成後續 Django ingestion 可以讀的 crawler adapter contract，但還沒有開始 Django、SQLite、scheduler、UI 或 Docker Compose。

已穩定的 crawler contract 包含：

- 型錄頁總數、分頁資訊、concept ID、名稱、product IDs 與圖片 URL。
- 正規化價格狀態：`FREE`、`PAID`、`DISCOUNTED`、`PS_PLUS`、`UNAVAILABLE`、`NOT_PURCHASABLE`、`UNKNOWN`。
- 金額欄位與原始顯示文字並存，包含 `base_amount_cents`、`discounted_amount_cents`、`plus_amount_cents`、`base_display`、`discounted_display`、`discount_text`、`service_branding` 與 `upsell_text`。
- typed parser errors，讓 embedded state 缺失、必要欄位缺失、cache ambiguity 這些失敗不會全部糊成同一鍋迷霧湯。
- catalog-first/detail-fallback source strategy，daily snapshot 先信明確 catalog price，只有缺資料或高風險狀態才查 concept detail。
- deterministic fixtures 與 offline CI，讓測試不用靠 PlayStation Store 當場心情。

下一個里程碑是 Django data foundation，而且只能在 crawler contract stabilization 的離線驗證通過後開始。下一步應只接資料基礎：Django models、SQLite persistence、sync run/error records 與 ingestion boundary。不要在這個交接點順手塞 scheduler、UI、auth、通知或 full detail backfill，這種「順手」通常就是專案管理的香蕉皮。

## Canonical setup and verification

本 repo 以 `uv` 作為本機與 CI 共用的可重現路徑。

```bash
uv sync --extra dev
uv run pytest -v
```

CI policy：GitHub Actions 只跑離線測試。CI 使用 `uv sync --extra dev --locked` 與 `uv run pytest -v`，不執行 live PlayStation Store crawler commands，也不 capture fixture。

## Manual crawler commands

這些命令會觸碰 live PlayStation Store，適合人工 smoke test 或 fixture refresh，不是 CI requirement。

```bash
uv run ps-price-crawler catalog --pages 2 --format json
uv run ps-price-crawler concept 223118 --format json
uv run ps-price-crawler fixture-targets --pages 80 --output .sisyphus/evidence/task-3-fixture-targets.json
uv run ps-price-crawler fixture-report --fixtures tests/fixtures/ps_store --output .sisyphus/evidence/fixture-report.json
```

`fixture-report` 讀 committed fixtures，屬於離線檢查；`catalog`、`concept` 與 `fixture-targets` 會讀 live site，應手動執行並保存 evidence。

## Fixture coverage

Committed fixtures 位於 `tests/fixtures/ps_store/`，目前覆蓋：

- `FREE`
- `PAID`
- `DISCOUNTED`
- `PS_PLUS`
- `UNKNOWN` 作為 unavailable/not-purchasable 風險區的 deterministic fallback

raw live captures 應保留在 ignored `tests/fixtures/live/`，不要 commit。committed fixture HTML 必須維持小檔案，並搭配 JSON metadata 記錄 catalog price fields、source URL、parser result 與 raw HTML hash/size。

## Snapshot source strategy

Daily price snapshots 採 catalog-first/detail-fallback。

使用 catalog 作為 snapshot source 的條件：

- normalized state 是 `FREE`、`PAID` 或 `DISCOUNTED`。
- catalog item 有 product IDs。

改查 concept detail 的條件：

- normalized state 是 `UNKNOWN`、`PS_PLUS`、`UNAVAILABLE` 或 `NOT_PURCHASABLE`。
- catalog item 缺 product IDs。
- 後續 Django ingestion 需要 `publisher_name`、`release_date` 或 `top_category`，但 catalog 物件沒有這些欄位。

這個策略避免把 7,990 個商品全部 detail backfill。全量 backfill 不是本里程碑的答案，硬做只會把 crawler 變成穿登山靴的資料庫 migration。

## Data source risk

crawler 從 PlayStation Store 台灣 SSR 頁面讀資料：

- 型錄：`/zh-hant-tw/category/28c9c2b2-cecc-415c-9a08-482a605cb104/{page}`
- concept 詳情：`/zh-hant-tw/concept/{conceptId}`

parser 會讀取嵌入的 `__NEXT_DATA__` 與 `env:*` JSON script payload。這是 PlayStation Store 網站的非公開實作細節，因此來源 schema drift 仍然是外部風險。typed parser errors 與 fixtures 只能讓壞掉時更早、更清楚地壞掉，不能把非公開來源變成合約 API，魔法還沒上班。

## Next milestone input

Django data foundation 可以先依賴這些 crawler fields：

- concept ID。
- product IDs when present。
- concept/product names。
- normalized price state。
- currency、amount cents 與 display fields。
- publisher、release date、top category from concept detail where parsed。
- source strategy decision，包含 `source`、`reason`、`reason_codes`、`normalized_state`、`product_ids` 與 `missing_metadata_fields`。
- parser error type/message。

仍視為 source-risk 的欄位與語意：

- PS Plus effective price semantics。
- unavailable 與 not purchasable 的細部分界。
- missing product IDs 或 missing `defaultProduct`。
- SSR schema drift。
- localized display text 與 currency parsing。
- concept detail price absence。
