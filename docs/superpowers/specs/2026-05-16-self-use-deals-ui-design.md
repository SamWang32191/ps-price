# PS Price 自用查價 UI 設計

日期：2026-05-16

## 目標

建立第一版自用查價 UI，讓目前已落地的 PlayStation Store 台灣商品與每日價格快照可以被直接查詢。這個里程碑聚焦「找特價清單」，先把已同步資料變成可瀏覽、可搜尋、可檢查歷史低價的頁面。

第一版重點是：

- 顯示一般可購買折扣商品清單。
- 依折扣幅度由大到小排序。
- 提供薄商品詳情頁，顯示目前價格、一般歷史最低價與每日快照表。
- 保持 UI 層只讀，不觸發同步、不寫入資料庫。

## 已確認範圍

- 使用 Django server-rendered pages。
- 不新增前端框架。
- 不先做 JSON API。
- 不新增資料表。
- 不把 PS Plus 專屬價混入一般折扣清單或一般歷史低價。
- 第一版詳情頁不做折線圖。
- 第一版不做分類覆寫、登入、通知、願望清單、同步重跑 UI。

## 架構與邊界

新增一個很薄的頁面邊界，建議命名為 `ps_price_web` app。

`ps_price_web` 負責：

- URL routing。
- Django views。
- Templates。
- 查價 UI 所需的 read-only query helper。
- 顯示用格式化 helper。

`ps_price_web` 不負責：

- crawler parsing。
- ingestion。
- scheduler。
- management command orchestration。
- 寫入 `StoreProduct`、`PriceSnapshot`、`SyncRun` 或 `SyncError`。

這個邊界避免把既有 `ps_price_sync` app 從同步/落地語意擴張成頁面層。UI 只讀既有 `StoreProduct` 與 `PriceSnapshot`。

## 頁面

### `/deals/`

折扣商品清單，也是第一版 MVP 的主要入口。

資料來源是每個 `StoreProduct` 最新一筆 `PriceSnapshot`。第一版只列一般折扣，不列 PS Plus 專屬價。

納入條件：

- 最新 snapshot 的 `normalized_state = DISCOUNTED`。
- `base_amount_cents` 存在。
- `discounted_amount_cents` 存在。
- `base_amount_cents > 0`。
- `discounted_amount_cents < base_amount_cents`。
- `StoreProduct.is_visible` 不是 `false`。

`is_visible = null` 不排除，避免 snapshot-first 建立但尚未完成 catalog visibility 的商品被誤藏。

預設排序：

1. 折扣幅度最大優先。
2. 折扣幅度相同時，可用商品名稱穩定排序。

折扣幅度計算：

```text
(base_amount_cents - discounted_amount_cents) / base_amount_cents
```

清單欄位：

- 封面。
- 商品名稱。
- 平台 raw 顯示。
- 原價。
- 折扣價。
- 折扣百分比。
- snapshot date。
- 商品詳情連結。
- PS Store source URL 連結，如果有資料。

搜尋：

- 提供一個簡單搜尋框。
- 對 `product_name` 與 `concept_name` 做 case-insensitive contains。
- 第一版不做分類、平台、多欄排序或進階篩選。

空狀態：

- 沒有折扣商品時顯示空狀態。
- 搜尋沒有結果時顯示空狀態。
- 空狀態不是錯誤。

### `/products/<product_id>/`

薄商品詳情頁。找不到商品時回 404。

內容分成三塊：

1. 商品基本資訊
   - 封面。
   - 商品名稱。
   - concept name。
   - publisher。
   - 平台 raw 顯示。
   - PS Store source URL。

2. 價格摘要
   - 最新 snapshot 的狀態與價格。
   - 一般歷史最低價。
   - 一般歷史最低價的 snapshot date。

3. 每日快照表
   - 依 `snapshot_date` 倒序列出。
   - 顯示狀態、原價、折扣價、PS Plus 價、折扣文字與 source strategy。

沒有 snapshot 時：

- 詳情頁仍正常顯示商品基本資訊。
- 價格摘要顯示尚無價格快照。
- 每日快照表顯示空狀態。

第一版不做 pagination。若資料累積後單一商品快照量造成頁面過重，再補分頁。

## 一般歷史最低價

一般歷史最低價只計算可直接購買的數字價格。

納入狀態：

- `PAID`
- `DISCOUNTED`

價格來源：

- `DISCOUNTED` 使用 `discounted_amount_cents`。
- `PAID` 使用 `base_amount_cents`。

排除狀態：

- `PS_PLUS`
- `FREE`
- `UNAVAILABLE`
- `NOT_PURCHASABLE`
- `UNKNOWN`

這避免把會員價、免費狀態或不可購買狀態混入一般歷史低價。

## 顯示格式

金額：

- 有 amount cents 時，以 TWD 顯示整數金額。
- 若 amount cents 缺失但 display 欄位存在，可顯示原始 display 文字。
- 若兩者都缺失，顯示空值佔位。

JSON raw 欄位：

- `platforms_raw`、`service_branding_raw`、`source_strategy_reason_codes_raw` 顯示前可嘗試解析 JSON。
- 解析失敗時直接顯示原字串，不讓頁面壞掉。

圖片：

- 有 `image_url` 時顯示封面。
- 沒有圖片時顯示簡單佔位，不回 500。

## 錯誤處理

- `/deals/` 沒有資料時顯示空狀態。
- `/products/<product_id>/` 找不到商品時回 404。
- 商品沒有 snapshot 時仍可正常顯示詳情。
- raw JSON 欄位解析失敗時回退顯示原字串。
- 查價 UI 不捕捉或吞掉同步錯誤；同步錯誤仍由既有 `SyncRun` 與 `SyncError` 承擔。

## 測試策略

測試集中在 query 與 view 行為。

至少涵蓋：

- `/deals/` 只列一般折扣商品。
- `/deals/` 不列 `PS_PLUS` 商品。
- `/deals/` 不列 `is_visible = false` 商品。
- `/deals/` 折扣幅度排序正確。
- `/deals/` 搜尋可匹配 `product_name`。
- `/deals/` 搜尋可匹配 `concept_name`。
- `/products/<product_id>/` 可顯示商品基本資訊。
- 詳情頁一般歷史最低價不混入 PS Plus 價格。
- 詳情頁一般歷史最低價不混入免費狀態。
- 找不到商品時回 404。
- 沒有 snapshot 的商品詳情頁可正常顯示。
- raw JSON 欄位解析失敗時頁面不回 500。

驗證命令：

```bash
uv run pytest -q
```

## 成功標準

- 可以用 Django dev server 打開 `/deals/`。
- `/deals/` 顯示一般折扣商品，且預設按折扣幅度排序。
- `/deals/` 可用商品名稱或 concept name 搜尋。
- 清單中的商品可連到 `/products/<product_id>/`。
- 詳情頁可顯示目前價格、一般歷史最低價與每日快照表。
- PS Plus 專屬價不混入一般折扣清單或一般歷史最低價。
- UI 層不寫入資料庫、不觸發同步。
- `uv run pytest -q` 通過。
