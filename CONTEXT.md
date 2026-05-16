# PS Price

追蹤台灣 PlayStation Store 商品與每日價格快照的單一領域語彙表，用來固定資料模型、同步流程與文件中的核心術語。

## Language

**Product**:
可購買的 PlayStation Store 商品實體，以 `product_id` 識別。
_Avoid_: 商品, StoreProduct, purchasable item

**Concept**:
分組一個或多個 **Product** 的 PlayStation Store 上層內容實體，以 `concept_id` 識別。
_Avoid_: 商品, title, game

**Publisher**:
PlayStation Store 來源資料提供的發行者名稱字串。
_Avoid_: normalized publisher, publisher master

**PriceSnapshot**:
某個 **Product** 在某個 `snapshot_date` 的單日價格觀測結果。
_Avoid_: 價格事件, 價格期間, effective price window

**SyncRun**:
一次手動或排程觸發的同步批次。
_Avoid_: 單筆同步, item sync, retry record

**SyncError**:
某次 **SyncRun** 內某個 **Product** 或某個來源項目未能成功落地的失敗紀錄。
_Avoid_: parser log, raw exception, debug output

**Catalog Sync**:
只更新 **Product** 主檔與可見性的同步批次，不產生 **PriceSnapshot**。
_Avoid_: full sync, price sync

**Snapshot Sync**:
會為 **Product** 寫入當日 **PriceSnapshot** 的同步批次。
_Avoid_: catalog refresh, metadata-only sync

**Observed Catalog Item**:
在一次 **Catalog Sync** 中被 crawler 觀測到的 catalog 項目，不保證可落成 **Product**。
_Avoid_: persisted product, saved item

**Persisted Product**:
成功落地成資料庫主檔的 **Product**。
_Avoid_: observed item, raw catalog entry

**Catalog Visibility**:
某個 **Product** 在最近一次 **Catalog Sync** 是否被觀測到。
_Avoid_: purchasable, active price, reachable detail page

**Missing Count**:
某個 **Product** 連續幾次 **Catalog Sync** 沒有被觀測到的次數。
_Avoid_: total missing times, sync error count, failure count

**Snapshot Date**:
一次 **Snapshot Sync** 的價格觀測要歸屬到哪一天的台北日期。
_Avoid_: source page date, write timestamp, event time

## Relationships

- 一個 **Concept** 可以對應一個或多個 **Product**
- 一個 **Product** 至多屬於一個 **Concept**
- 一個 **Product** 可以對應零個或一個 **Publisher** 字串值
- 一個 **Product** 可以擁有多個 **PriceSnapshot**
- 一個 **PriceSnapshot** 只屬於一個 **Product**
- 一個 **SyncRun** 可以包含多個 **Product** 的同步處理
- 一個 **SyncRun** 可以產生多筆同步錯誤
- 一筆 **SyncError** 必定屬於一個 **SyncRun**
- 一次 **Catalog Sync** 是一種 **SyncRun**
- 一次 **Snapshot Sync** 是一種 **SyncRun**
- 一個 **Observed Catalog Item** 可能不會成為 **Persisted Product**
- 一個 **Persisted Product** 來自至少一個 **Observed Catalog Item**
- 一個 **Product** 的 **Catalog Visibility** 由最近一次 **Catalog Sync** 決定
- 一個 **Product** 的 **Missing Count** 隨 **Catalog Sync** 結果遞增或歸零
- 一個只經過 **Snapshot Sync** 建立、尚未進入 **Catalog Sync** 追蹤的 **Product**，其 **Catalog Visibility** 與 **Missing Count** 仍為未知
- 一個 **PriceSnapshot** 以 **Snapshot Date** 識別其日層級觀測歸屬

## Example dialogue

> **Dev:** 「這次價格快照要掛在 **Concept** 還是 **Product**？」
> **Domain expert:** 「掛在 **Product**，因為可購買性與實際售價是 product 層級；**Concept** 只負責分組。」

## Flagged ambiguities

- 「商品」曾同時指 **Concept** 與 **Product**；已解決：本專案中的「商品」預設指 **Product**，除非明確寫出 **Concept**。
- 「PriceSnapshot」曾可能被理解成價格變更事件；已解決：它是某日的單次觀測結果，不表示當天內的價格變動歷程。
- **PriceSnapshot** 不只記錄數字價格；`UNAVAILABLE`、`NOT_PURCHASABLE`、`PS_PLUS`、`UNKNOWN` 也屬於合法觀測結果。
- 「SyncRun」曾可能被理解成單筆商品同步；已解決：它表示一次批次執行，不是單一商品層級的嘗試。
- 「SyncError」曾可能被理解成一般程式例外輸出；已解決：它是批次內可追蹤、可重跑的失敗紀錄。
- 「同步」曾可能混指 metadata refresh 與價格落地；已解決：**Catalog Sync** 不產生 **PriceSnapshot**，**Snapshot Sync** 才會。
- catalog 覆蓋率曾可能只看成功落地筆數；已解決：**Observed Catalog Item** 與 **Persisted Product** 必須分開計數。
- `is_visible` 曾可能混指可購買性或頁面可達性；已解決：它只表示 **Catalog Visibility**，不表示價格狀態。
- `missing_count` 曾可能被理解成累積缺席或失敗總數；已解決：它是連續缺席次數，重新被觀測到就歸零。
- 由 detail 路徑先建立的 **Product** 不應被預設成已納入 catalog 追蹤；已解決：在第一次 **Catalog Sync** 命中前，**Catalog Visibility** 與 **Missing Count** 都是未知。
- `snapshot_date` 曾可能與寫入時間或來源頁日期混用；已解決：它是台北時區下的日層級歸屬日期。
