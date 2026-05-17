# Watchlist + Target Price 設計

日期：2026-05-17

## 目標

建立第一版自用追蹤清單，讓使用者可以在商品詳情頁追蹤關心的遊戲，設定一般購買價格的目標價，並在 `/watchlist/` 集中查看哪些商品已經達標。

這個里程碑聚焦「我關心的遊戲現在是否值得買」：

- 每個商品最多一筆 watchlist 記錄。
- 商品詳情頁可加入追蹤、更新目標價、移除追蹤。
- `/watchlist/` 顯示所有追蹤商品與達標狀態。
- target price 只用一般購買價格判定，不納入 PS Plus 價格。

## 已確認範圍

- 使用資料庫內建 watchlist，不使用外部 JSON/YAML 設定檔。
- 新增持久化 `WatchedProduct` model。
- `ps_price_web` 負責頁面、表單與 query helper。
- 商品 detail 頁是唯一新增或更新 watchlist 的入口。
- 新增 `/watchlist/` read-only 清單頁。
- target price 以台幣元輸入，後端存 cents。
- target price 可留空，表示只追蹤但不設定達標門檻。
- `0` 或負數 target price 是 invalid。

## 明確不做

- 不做帳號或多使用者；這是單人自架資料。
- 不做通知、email、LINE 或 webhook。
- 不做 PS Plus target 判定。
- 不做手動輸入 product ID 的 watchlist 新增入口。
- 不做 dashboard summary。
- 不做價格歷史圖表。
- 不改 crawler、sync runner 或 scheduler。

## 架構與邊界

新增 `WatchedProduct` model 放在 `ps_price_sync.models`。它是持久化 app data，且直接關聯既有 `StoreProduct`。這個 model 不屬於 crawler，也不影響 ingestion 或 scheduler。

`ps_price_web` 負責：

- `/watchlist/` route。
- 商品 detail 頁的 watchlist 表單。
- watchlist query helper。
- target price parsing 與 validation。
- 達標狀態計算。

`ps_price_web` 不負責：

- 抓取 PlayStation Store。
- 寫入 `PriceSnapshot`。
- 修改同步流程。
- 通知排程。

這個邊界讓 watchlist 成為 UI 層可寫入的使用者資料，但不污染既有價格同步邏輯。

## 資料模型

新增 `WatchedProduct`：

- `store_product`: `OneToOneField(StoreProduct, on_delete=CASCADE, related_name="watch")`
- `target_price_cents`: nullable positive integer
- `note`: optional text
- `created_at`
- `updated_at`

一個 `StoreProduct` 最多只能有一筆 `WatchedProduct`。刪除商品時，對應 watchlist 記錄會 cascade 移除。

`target_price_cents = null` 表示已追蹤但未設定目標價。第一版 model 保留 `note` 欄位給未來自用備註，但 MVP UI 不顯示也不編輯 `note`。

## Target Price 判定

target price 只看最新 snapshot 的一般購買價格。

可判定狀態：

- `DISCOUNTED`: 使用 `discounted_amount_cents`
- `PAID`: 使用 `base_amount_cents`

不可判定狀態：

- `PS_PLUS`
- `FREE`
- `UNAVAILABLE`
- `NOT_PURCHASABLE`
- `UNKNOWN`
- 沒有 snapshot
- 最新 snapshot 沒有可用金額

達標規則：

- 有 target price，且最新一般購買價小於或等於 target price，狀態為 `達標`。
- 有 target price，且最新一般購買價高於 target price，狀態為 `未達標`。
- 已追蹤但沒有 target price，狀態為 `未設定目標價`。
- 沒有可用一般購買價，狀態為 `無一般價格`。

PS Plus 價格不會讓商品達標，即使 plus 價低於 target price。

## 商品詳情頁行為

`/products/<product_id>/` 保持既有 URL，新增 Watchlist 區塊。

未追蹤商品：

- 顯示 target price 表單。
- 提交有效 target price 後建立 `WatchedProduct`。
- target price 空白時仍建立 watchlist 記錄。

已追蹤商品：

- 顯示目前 target price。
- 再次提交會更新 target price。
- 顯示目前 watch 狀態。
- 提供移除追蹤 action。

表單語意：

- 輸入單位是台幣元，例如 `590`。
- 後端存 `59000` cents。
- 空白 target price 存 `null`。
- `0` 或負數顯示 validation error，不建立或更新 watchlist。
- 移除追蹤只刪除 `WatchedProduct`，不刪商品或價格快照。

## `/watchlist/` 頁面

`/watchlist/` 顯示所有追蹤商品。

每列顯示：

- 商品名稱。
- 商品 detail 頁連結。
- 最新一般購買價。
- target price。
- watch 狀態。

狀態：

- `達標`
- `未達標`
- `無一般價格`
- `未設定目標價`

排序：

1. `達標`
2. `未達標`
3. `無一般價格`
4. `未設定目標價`
5. 同組內依商品名稱排序

沒有追蹤商品時顯示 empty state，不回 404。

## 錯誤處理

- 商品不存在時，既有 detail 頁仍回 404。
- invalid target price 顯示表單錯誤，且不寫入資料庫。
- 沒有 snapshot 的追蹤商品仍可顯示在 `/watchlist/`。
- 最新 snapshot 是 `PS_PLUS` 時顯示 `無一般價格`，不以 plus 價判定達標。
- 移除不存在的 watchlist 記錄不應刪除商品；第一版可回到 detail 頁並顯示未追蹤狀態。

## 測試策略

測試集中在 model、query helper 與 view 行為。

至少涵蓋：

- `WatchedProduct` 與 `StoreProduct` 是一對一。
- 刪除 `StoreProduct` 會 cascade 刪除 `WatchedProduct`。
- `DISCOUNTED` 使用 `discounted_amount_cents` 判定達標。
- `PAID` 使用 `base_amount_cents` 判定達標。
- `PS_PLUS` 不算達標價格。
- 沒有 target price 時狀態為 `未設定目標價`。
- 沒有一般購買價格時狀態為 `無一般價格`。
- `/watchlist/` empty state。
- `/watchlist/` 顯示追蹤商品並依狀態排序。
- detail 頁可新增 watchlist。
- detail 頁可更新 target price。
- detail 頁可移除 watchlist。
- invalid target price 顯示錯誤且不寫入。

驗證命令：

```bash
uv run pytest -q
```

## 成功標準

- 可以從商品 detail 頁加入追蹤。
- 可以從商品 detail 頁更新或清空 target price。
- 可以從商品 detail 頁移除追蹤。
- `/watchlist/` 顯示所有追蹤商品。
- `/watchlist/` 能區分達標、未達標、無一般價格與未設定目標價。
- PS Plus 價格不會被算進 target price 達標判定。
- crawler、sync runner 與 scheduler 行為不變。
- `uv run pytest -q` 通過。
