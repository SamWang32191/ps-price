# PS Price Daily Sync Scheduler 設計

日期：2026-05-16

## 目標

建立第一版每日自動同步排程器，讓既有 Django data foundation 不再只靠人工執行 `sync_ps_store`，而是能每天固定產生 `PriceSnapshot`，持續累積歷史價格資料。

這個 feature 的重點是：

- 每天自動執行一次全 catalog 的 `catalog-and-snapshot` 同步。
- 沿用既有 `SyncRun`、`SyncError`、ingestion service 與 crawler contract。
- 讓排程行為可以在本機或未來 Docker Compose scheduler service 中重複啟動。
- 保持排程層薄而可替換，不把 UI、通知或 retry queue 塞進同一個 feature。

## 已確認範圍

- 排程器只負責觸發既有 management command，不重新實作同步邏輯。
- 預設同步模式是 `catalog-and-snapshot`。
- 每日排程應從 catalog 第 1 頁開始同步到 `CatalogPage.is_last == true`，不使用固定 5 頁作為 production coverage。
- 排程需提供 `max-pages` 安全上限，避免來源 pagination schema drift 造成無界抓取。
- `snapshot_date` 預設使用台北時區的當日日期。
- 預設每日 03:30 台北時間執行一次，實際時間需可由環境變數設定。
- 每次執行仍由 `sync_ps_store` 建立 `SyncRun` 並寫入 `SyncError`。
- `SyncRun.summary` 應補上全 catalog 同步的 coverage 欄位，讓後續 Dashboard 能判斷是否真的跑到最後一頁。
- 若一次同步失敗，排程器應記錄失敗並等待下一次排程；本 feature 不做自動補跑佇列。

## 非目標

這個 feature 不做：

- Dashboard 或商品查詢頁。
- Django admin 客製頁。
- Dockerfile 或 Docker Compose scheduler service。
- 通知系統。
- `SyncError` 單筆重跑 UI 或 retry queue。
- full detail backfill。
- crawler parser 或 source strategy 重寫。
- 同步請求併發化。
- 多區商店同步。
- 歷史低價查詢演算法。
- 多 scheduler process 的分散式鎖。

## 架構

新增一個很薄的 scheduler boundary，位置在 deployment / command orchestration 層，不進入 crawler adapter 或 ingestion service。

元件：

1. `run_daily_sync_scheduler` management command
   - 作為第一版 scheduler entrypoint。
   - 由 Python/Django command 包裝既有 `sync_ps_store`。
   - 負責計算預設 `snapshot_date`。
   - 負責讀取 `PS_PRICE_SYNC_MAX_PAGES`、`PS_PRICE_SYNC_MODE`、`PS_PRICE_SYNC_TIMEZONE`、`PS_PRICE_SYNC_AT` 這類設定。

2. `scheduler process`
   - 第一版使用單一長駐 Django command loop。
   - 到達排程時間後用 Django `call_command` 呼叫既有 `sync_ps_store`。
   - 若程序重啟，不補跑過去錯過的時間點；下一次排程自然執行。
   - 第一版假設部署時只啟動一個 scheduler process，不實作跨程序分散式鎖。

3. `existing sync command`
   - 繼續由 `sync_ps_store` 管理 `SyncRun` 生命週期。
   - 繼續由 `sync_runner` 執行 catalog / snapshot orchestration。
   - 需要支援 `until-last` catalog traversal，讓 scheduler 不必事先知道總頁數。
   - 繼續由 ingestion service 寫入 `StoreProduct`、`PriceSnapshot`、`SyncError`。

這個分層讓未來要換成 host cron、Docker Compose scheduler、systemd timer 或雲端排程時，只需要替換 scheduler process，不需要改同步核心。

## 設定

第一版設定應保持少量且明確：

- `PS_PRICE_SYNC_MODE`
  - 預設：`catalog-and-snapshot`
  - 允許值沿用 `sync_ps_store --mode`
- `PS_PRICE_SYNC_MAX_PAGES`
  - 預設：`500`
  - 必須是大於等於 1 的整數
  - 只作為 safety guard，不代表每日同步應只抓固定頁數
  - 目前 spike 觀測 catalog 約 7,990 筆、每頁約 24 筆，約 333 頁；`500` 是保守上限，不是目標頁數
- `PS_PRICE_SYNC_TIMEZONE`
  - 預設：`Asia/Taipei`
- `PS_PRICE_SYNC_AT`
  - 預設：`03:30`
  - 格式固定為 `HH:MM`

`snapshot_date` 不建議做成必填設定。每日排程的主要語意是「台北日期當天的價格觀測」，手動補資料仍應使用現有 command 明確指定 `--snapshot-date`。

## Summary Coverage

既有 `SyncRun.summary` 仍保存 JSON text。本 feature 應在既有 `observed_items`、`persisted_products`、`skipped_missing_product_id` 之外，補上以下欄位：

- `pages_fetched`
- `last_page_reached`
- `max_pages_hit`
- `last_page_number`
- `catalog_total_count`

這些欄位只描述本次 catalog traversal 的 coverage，不替代 `success_count`、`error_count` 或 `SyncError`。

## 執行流程

每日排程觸發時：

1. 讀取環境設定。
2. 以 `PS_PRICE_SYNC_TIMEZONE` 計算今天的 `snapshot_date`。
3. 呼叫：

   ```bash
   python manage.py sync_ps_store --mode <mode> --until-last --max-pages <max-pages> --snapshot-date <yyyy-mm-dd>
   ```

4. 由既有 command 建立 `SyncRun`，並在結束時標記 `succeeded`、`partial` 或 `failed`。
5. `sync_ps_store` 從第 1 頁同步到 `CatalogPage.is_last == true`，但不得超過 `max-pages`。
6. scheduler process 將 command exit code 寫入標準輸出或容器 log。
7. 若 command 失敗，scheduler process 不立即進入 retry loop，避免連續打來源站；等待下一次排程。

## 錯誤處理

- `sync_ps_store` 內部已能把單筆 snapshot 失敗寫成 `SyncError`，scheduler 不重複保存單筆錯誤。
- command 若整批失敗，`SyncRun.status` 應維持既有失敗語意。
- 若已達 `max-pages` 仍未遇到 `is_last`，command 應保存清楚錯誤訊息；若已有成功落地資料，`SyncRun.status` 應為 `partial`，若完全沒有成功落地，則為 `failed`。
- 第一版維持既有 `PlayStationStoreClient` 的低速序列請求節奏，不新增並行抓取。
- scheduler 應避免同一程序內重疊執行兩次同步；若上一輪仍在跑，下一輪應跳過並寫 log。第一版不保證多個 scheduler process 之間互斥，部署設定必須只啟動一個 scheduler process。
- 本 feature 不處理 missed run 補償。需要補資料時，由人工執行現有 command 指定 `--snapshot-date`。

## 測試策略

至少要有以下測試：

- scheduler entrypoint 能依台北時區計算預設 `snapshot_date`。
- 環境變數能正確覆蓋 mode、max-pages、timezone 與排程時間。
- max-pages 小於 1 或時間格式錯誤時，會產生清楚錯誤。
- `sync_ps_store --until-last` 會持續抓頁直到 parser 回傳 `is_last == true`。
- 達到 max-pages 仍未遇到 `is_last` 時，會以可觀測錯誤結束。
- summary 會記錄 `pages_fetched`、`last_page_reached`、`max_pages_hit`、`last_page_number` 與 `catalog_total_count`。
- 排程觸發時會呼叫既有 `sync_ps_store` 入口，且參數正確。
- 上一輪仍在執行時，不會重疊啟動下一輪。
- 不依賴 live PlayStation Store；測試只 mock command 呼叫或 service boundary。

## 成功標準

- 可以用一個明確入口啟動每日同步排程器。
- scheduler 每天產生一次全 catalog 的 `catalog-and-snapshot` 同步。
- 每次同步仍可在 `SyncRun` 查到狀態與計數。
- 每次全 catalog 同步都能從 `SyncRun.summary` 查到 coverage 證據。
- 單筆錯誤仍落在 `SyncError`，不會被 scheduler 吃掉。
- 排程器重啟後可繼續工作。
- `uv run --extra dev pytest -q` 通過。
- 未來接 Docker Compose scheduler service 時，不需要拆改 crawler 或 ingestion 核心。
