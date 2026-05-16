# PS Price Django Data Foundation 設計

日期：2026-05-16

## 目標

在既有 crawler contract stabilization 之上，建立第一版 Django data foundation，讓 PlayStation Store 的結構化 crawler 結果可以可靠寫入 SQLite，並留下可追蹤的同步批次與錯誤紀錄。

這個里程碑的重點是：

- 把商品資料與每日價格快照落地。
- 保證同一天重跑不會產生重複快照。
- 保留同步批次與單筆錯誤的可觀測性。
- 維持 crawler parser 與 Django ORM 之間的清楚邊界。

## 已確認範圍

- 技術方向維持 Django + SQLite。
- Django 只接結構化 crawler contract，不碰 HTML 解析。
- 商品主體以 `product_id` 為準，`concept_id` 作為群組與來源欄位保留。
- 如果 catalog 項目暫時缺 `product_id`，不建立正式商品資料，改記 `SyncError` 與批次摘要。
- 本里程碑包含：
  - Django app skeleton。
  - `StoreProduct`、`PriceSnapshot`、`SyncRun`、`SyncError` models 與 migrations。
  - ingestion service。
  - 一個可手動執行的 Django management command。
- 本里程碑不包含：
  - scheduler。
  - UI 或 dashboard。
  - Django admin 客製頁面。
  - live crawler orchestration 的大幅重構。
  - full detail backfill。

## 架構與邊界

這個里程碑分成三層：

1. `crawler adapter`
   - 沿用既有 `ps_price_crawler` 模組。
   - 負責抓取、解析、價格正規化與 source strategy。
   - 對 Django 輸出 `CatalogItem`、`ProductDetail`、`NormalizedPrice`、`SnapshotSourceDecision` 等結構化資料。

2. `ingestion service`
   - 位於 Django app 內的 application service。
   - 負責把 crawler contract 轉成 ORM upsert 與 snapshot 寫入。
   - 負責更新 `SyncRun` / `SyncError` 計數與摘要。

3. `management command`
   - 提供手動執行入口。
   - 負責建立同步批次、協調 service 呼叫、回報執行結果。
   - 不直接解析 HTML，不持有 parser 細節。

設計原則是讓 parser 問題停在 adapter，資料一致性停在 ingestion，執行入口停在 command。未來要接 scheduler，只需要呼叫 command，不需要把 scheduler 直接耦合到 crawler internals。

## 資料模型

### StoreProduct

用途：保存可持續追蹤的商店商品主體。

建議欄位：

- `id`
- `product_id`
  - unique
- `concept_id`
  - indexed
  - 可為空，不作為落地必備條件
- `product_name`
- `concept_name`
  - 保留來源的 concept 標籤，支援後續人工排查與群組比對
- `publisher_name`
  - 視為來源提供的 raw publisher string，不先正規化或拆成獨立資料表
- `release_date_raw`
  - 視為來源提供的 raw release date string，不做格式解析或回寫
- `top_category`
  - 視為來源提供的 raw category label，不等於站內本地分類
- `image_url`
- `source_url`
  - 保存目前最穩定、可重新打開的商品頁 URL
  - 採 last-non-empty-wins
- `platforms_raw`
  - 第一版先存 JSON text，不先正規化成關聯表
- `is_visible`
  - 由 `Catalog Sync` 建立時可初始化為 true
  - 若首次由 `Snapshot Sync` 建立，應先保持 unknown/null
- `missing_count`
  - 若已進入 `Catalog Sync` 追蹤，表示連續缺席次數
  - 若首次由 `Snapshot Sync` 建立，應先保持 unknown/null
- `last_seen_at`
  - 只在 `Catalog Sync` 觀測到此 product 時更新
- `created_at`
- `updated_at`

### PriceSnapshot

用途：保存單一商品單一天的價格狀態。

這是日層級價格觀測結果，不是價格變更事件；`UNAVAILABLE`、`NOT_PURCHASABLE`、`PS_PLUS`、`UNKNOWN` 也屬於合法 snapshot。

建議欄位：

- `id`
- `store_product`
  - foreign key to `StoreProduct`
- `snapshot_date`
  - 表示這次價格觀測要歸屬到哪一天的台北日期
- `normalized_state`
- `currency`
  - 第一版保留欄位，允許為空
  - 不在 schema 層強制只能是 `TWD`
- `base_amount_cents`
- `discounted_amount_cents`
- `plus_amount_cents`
- `base_display`
- `discounted_display`
- `discount_text`
- `service_branding_raw`
  - 第一版先存 JSON text
- `upsell_text`
- `source_strategy_source`
- `source_strategy_reason`
- `source_strategy_reason_codes_raw`
  - 第一版先存 JSON text
- `created_at`
- `updated_at`

補充：

- `PriceSnapshot` 不存 `source_url`；來源定位由 `StoreProduct` 與 `SyncError` 承擔
- `source_strategy_source`、`source_strategy_reason`、`source_strategy_reason_codes_raw` 只在 `Snapshot Sync` 的 `PriceSnapshot` 寫入，不寫回 `StoreProduct`

唯一限制：

- `(store_product, snapshot_date)` unique

### SyncRun

用途：保存一次同步批次的整體狀態。

建議欄位：

- `id`
- `sync_type`
  - 例如 `catalog_only`、`snapshot_only`、`catalog_and_snapshot`
- `status`
  - 例如 `running`、`succeeded`、`failed`、`partial`
  - `succeeded`：沒有 `SyncError`
  - `partial`：有成功落地，也有 `SyncError`
  - `failed`：沒有任何成功落地，且有錯誤
- `started_at`
- `finished_at`
- `success_count`
  - `Catalog Sync` 表示成功落成或成功更新的 `Persisted Product` 數
  - `Snapshot Sync` 表示成功寫入或成功更新的 `PriceSnapshot` 數
- `error_count`
- `summary`
  - 保存結構化 JSON text，而不是自由文字摘要
  - 至少應包含 `observed_items`、`persisted_products`、`skipped_missing_product_id`
- `created_at`
- `updated_at`

### SyncError

用途：保存同步過程中的單筆失敗，支援後續排查與重跑。

建議欄位：

- `id`
- `sync_run`
  - foreign key to `SyncRun`
- `stage`
  - 第一版先收斂為 `catalog_ingestion`、`snapshot_ingestion`
- `product_id`
- `concept_id`
- `source_url`
  - 保存當次失敗實際涉及的來源 URL
- `error_type`
- `error_message`
- `resolved_at`
  - 只表示後續已成功重跑或已明確判定不再需要處理
- `created_at`
- `updated_at`

唯一性原則：

- 不對 `SyncError` 設定跨批次唯一鍵
- 同一個 `product_id` 在不同 `SyncRun` 重複失敗時，應保留多筆歷史
- 同一個 `SyncRun` 中不同 `stage` 的失敗，也應保留為不同錯誤紀錄

## Ingestion 流程

### ingest_catalog_page

輸入：

- `CatalogPage`
- 目前的 `SyncRun`

行為：

- 逐筆處理 catalog item。
- 若 item 缺 `product_id`：
  - 不建立 `StoreProduct`。
  - 建立 `SyncError`。
  - 增加 `SyncRun.error_count`。
  - 這只表示本次 `Catalog Sync` 無法落地，不表示未來 detail 路徑永遠不能建立此 product。
- 若 item 有 `product_id`：
  - 以 `product_id` upsert `StoreProduct`。
  - 更新 `concept_id`、名稱、圖片、來源 URL、平台與可見性。
  - `product_name` 與 `concept_name` 採 last-write-wins，但 detail 路徑優先於 catalog 路徑。
  - `image_url` 採 last-non-empty-wins，不做歷史追蹤。
  - `source_url` 採 last-non-empty-wins，並以可重新打開商品頁為優先。
  - `platforms_raw` 採 last-non-empty-wins，只接受完整 JSON 陣列覆蓋，不做 union merge。
  - `publisher_name` 採 last-non-empty-wins，維持 raw source string。
  - `release_date_raw` 若出現在此路徑，採 last-non-empty-wins，且不做格式解析或回寫。
  - 若此 product 先前只由 `Snapshot Sync` 建立，這次第一次被 `Catalog Sync` 觀測到時，`is_visible` 應更新為 true，`missing_count` 應初始化為 0。
  - 更新 `last_seen_at`。
  - 把 `missing_count` 重設為 0。
- 對於本次 `Catalog Sync` 未觀測到、但資料庫已存在的 `Product`：
  - `is_visible` 應更新為 false
  - `missing_count` 應遞增 1
- 即使 catalog item 內含價格資訊，這個 use case 也不建立 `PriceSnapshot`。
- 這個 use case 只處理商品主檔與 catalog 層級資訊。
- `NormalizedPrice` 與 `SnapshotSourceDecision` 不屬於這個 use case 的輸入；如果要做 catalog coverage summary，應由 command 層另外統計。

### ingest_product_detail_snapshot

輸入：

- `ProductDetail`
- `NormalizedPrice`
- `SnapshotSourceDecision`
- `snapshot_date`
- 目前的 `SyncRun`

行為：

- 以 `product_id` 取得或建立 `StoreProduct`。
- 若 catalog 階段先前因缺 `product_id` 而未能落地，但這次 detail 已提供有效 `product_id`，仍應允許建立 `StoreProduct`。
- 補齊 `publisher_name`、`release_date_raw`、`top_category`、`product_name`、`concept_name`。
- `product_name` 與 `concept_name` 採 last-write-wins，且 detail 路徑優先於 catalog 路徑。
- `image_url` 採 last-non-empty-wins，不做歷史追蹤。
- `source_url` 採 last-non-empty-wins，並以可重新打開商品頁為優先。
- `platforms_raw` 採 last-non-empty-wins，只接受完整 JSON 陣列覆蓋，不做 union merge。
- `publisher_name` 採 last-non-empty-wins，維持 raw source string。
- `release_date_raw` 採 last-non-empty-wins，且不做格式解析或回寫。
- `top_category` 採 last-non-empty-wins，不做本地映射或保守 merge。
- 若此 product 是第一次由 `Snapshot Sync` 建立，`is_visible` 與 `missing_count` 應保持 unknown/null，直到後續第一次 `Catalog Sync` 命中後才轉成 true / 0。
- 不更新 `last_seen_at`，因為它只表示最近一次 `Catalog Sync` 的觀測時間。
- 依 `(store_product, snapshot_date)` upsert `PriceSnapshot`。
- 若同一天重跑：
  - 更新既有 snapshot，不新增第二筆。
- 無論這次觀測是數字價格或非數字價格狀態，都應寫入 `PriceSnapshot`。
- 寫入 source strategy 與原始顯示文字，保留後續除錯能力。

### ingest_catalog_snapshot

輸入：

- `CatalogItem`
- `NormalizedPrice`
- `SnapshotSourceDecision`
- `snapshot_date`
- 目前的 `SyncRun`

前提：

- 只在 `SnapshotSourceDecision.source == "catalog"` 時使用

行為：

- 以 `product_id` 取得或建立 `StoreProduct`。
- 若 catalog 階段已具備有效 `product_id`，應允許直接寫入 `PriceSnapshot`，不必強制先經過 detail。
- `product_name` 與 `concept_name` 採 last-write-wins，但 detail 路徑優先於 catalog 路徑。
- `image_url` 採 last-non-empty-wins，不做歷史追蹤。
- `source_url` 採 last-non-empty-wins，並以可重新打開商品頁為優先。
- `platforms_raw` 若此路徑沒有完整資料，允許維持既有值不覆蓋。
- `publisher_name`、`release_date_raw`、`top_category` 若此路徑沒有完整資料，允許維持既有值不覆蓋。
- 不更新 `last_seen_at`，因為它只表示最近一次 `Catalog Sync` 的觀測時間。
- 依 `(store_product, snapshot_date)` upsert `PriceSnapshot`。
- 若同一天重跑：
  - 更新既有 snapshot，不新增第二筆。
- 無論這次觀測是數字價格或非數字價格狀態，都應寫入 `PriceSnapshot`。
- 寫入 source strategy 與原始顯示文字，保留後續除錯能力。

## Management Command

第一版提供一個手動 command，例如 `sync_ps_store`。

支援模式：

- `catalog-only`
- `snapshot-only`
- `catalog-and-snapshot`

責任：

- 建立 `SyncRun` 並標記 `running`
- 逐步呼叫 adapter 與 ingestion service
- 捕捉單筆錯誤後建立 `SyncError`
- 在結束時把 `SyncRun.status` 更新為 `succeeded`、`partial` 或 `failed`

這個 command 是未來 scheduler 的接點，但本里程碑不實作 scheduler。

## 錯誤處理

- 單一商品 ingestion 失敗不應中斷整批同步。
- 缺 `product_id` 視為可觀測資料缺口，不是 schema 例外。
- parser 或 source strategy 傳入的錯誤型別與訊息應盡量原樣保存到 `SyncError`。
- `SyncRun.summary` 應保存結構化 JSON text，方便後續查詢、驗證與 UI 使用。
- 本里程碑不做自動 retry queue；重跑策略先留給後續 command/admin 階段。
- `created_at` 與 `updated_at` 只表示資料庫寫入時間，不表示資料新鮮度、來源日期或同步歸屬。

## 測試策略

至少要有以下測試：

- model constraint 測試：
  - `product_id` unique
  - `(store_product, snapshot_date)` unique
- ingestion 測試：
  - catalog item 可正確 upsert 成 `StoreProduct`
  - detail 可正確 upsert 成 `PriceSnapshot`
  - 同一天重跑只更新同一筆 snapshot
  - 缺 `product_id` 只記 `SyncError`，不建立商品
- command 測試：
  - `SyncRun` 狀態與成功/失敗計數正確
  - 單筆失敗不會讓整批直接崩潰
- adapter-to-ingestion 邊界測試：
  - 使用既有 fixtures 驗證 crawler contract 能餵進 Django，不依賴 live site

## 非目標

這個里程碑不做：

- Dashboard 或商品查詢頁
- admin 客製操作頁
- scheduler container
- 通知系統
- 全量歷史回填
- 自動分類覆寫 UI
- crawler parser 本身的大規模重寫

## 成功標準

- Django 專案可建立 SQLite schema。
- 結構化 crawler contract 可以寫入 `StoreProduct` 與 `PriceSnapshot`。
- 同一天重跑不會產生重複 snapshot。
- 每次手動同步都會留下 `SyncRun`。
- 單筆失敗會留下 `SyncError`，且不會中斷整批同步。
- 未來要接 scheduler 或 UI 時，不需要回頭拆 parser 與 ORM 的邊界。
