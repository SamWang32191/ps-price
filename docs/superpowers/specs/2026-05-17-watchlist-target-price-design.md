# Watchlist + Target Price 設計

日期：2026-05-17

## 目標

建立第一版自用追蹤清單，讓使用者可以在 Product detail 頁追蹤關心的 **Product**，設定 **General Purchase Price** 的目標價，並在 `/watchlist/` 集中查看哪些 **Watched Product** 已經達標。

這個里程碑聚焦「我關心的 **Product** 現在是否值得買」：

- 每個 **Product** 最多一筆 watchlist 記錄。
- Product detail 頁可建立 **Watched Product**、更新目標價、移除 **Watched Product**。
- `/watchlist/` 顯示所有 **Watched Product** 與達標狀態。
- target price 只用 **General Purchase Price** 判定，不納入 PS Plus 價格。

## 已確認範圍

- 使用資料庫內建 watchlist，不使用外部 JSON/YAML 設定檔。
- 新增持久化 `WatchedProduct` model。
- `ps_price_web` 負責頁面、表單與 query helper。
- Product detail 頁是唯一新增或更新 **Watched Product** 的入口。
- 新增 `/watchlist/` read-only 清單頁。
- target price 以台幣元輸入，後端存 cents。
- target price 可留空，表示建立 **Watched Product** 但不設定達標門檻。
- `0` 或負數 target price 是 invalid。

## 明確不做

- 不做帳號或多使用者；這是單人自架資料。
- 不新增 auth、session 或 CSRF middleware；MVP 不宣稱可作為公開安全寫入 UI。
- 不做通知、email、LINE 或 webhook。
- 不做 PS Plus target 判定。
- 不做手動輸入 product ID 的 watchlist 新增入口。
- 不做 `/watchlist/` 搜尋或篩選。
- 不做 dashboard summary。
- 不做價格歷史圖表。
- 不改 crawler、sync runner 或 scheduler。

## 架構與邊界

Implementation plan 與 implementation work 必須先閱讀 `CONTEXT.md`，並使用其中的 canonical terms，尤其是 **Watched Product** 與 **General Purchase Price**。

新增 `WatchedProduct` model 放在 `ps_price_web.models`。它是自用 UI 的偏好資料，直接關聯既有 `ps_price_sync.StoreProduct`，但不屬於同步資料。這個 model 不屬於 crawler，也不影響 ingestion 或 scheduler。

`ps_price_web` 負責：

- `/watchlist/` route。
- Product detail 頁的 watchlist 表單。
- watchlist query helper。
- target price parsing 與 validation。
- 達標狀態計算。

`ps_price_web` 不負責：

- 抓取 PlayStation Store。
- 寫入 `PriceSnapshot`。
- 修改同步流程。
- 通知排程。

這個邊界讓 watchlist 成為 `ps_price_web` 擁有的使用者偏好資料，不污染既有價格同步邏輯。

## 資料模型

新增 `WatchedProduct`：

- `store_product`: `OneToOneField(StoreProduct, on_delete=CASCADE, related_name="watch")`
- `target_price_cents`: nullable positive integer
- `created_at`
- `updated_at`

一個 `StoreProduct` 最多只能有一筆 `WatchedProduct`。刪除 `StoreProduct` 時，對應 `WatchedProduct` 會 cascade 移除。

`target_price_cents = null` 表示已建立 **Watched Product** 但未設定目標價。

**Catalog Visibility** 或 **Missing Count** 變化不會移除 **Watched Product**。只有 `StoreProduct` 實體被刪除時，對應 `WatchedProduct` 才會被 cascade 刪除。

## Target Price 判定

target price 只看最新 snapshot 的 **General Purchase Price**。

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

- 有 target price，且最新 **General Purchase Price** 小於或等於 target price，狀態為 `達標`。
- 有 target price，且最新 **General Purchase Price** 高於 target price，狀態為 `未達標`。
- 已建立 **Watched Product** 但沒有 target price，狀態為 `未設定目標價`。
- 沒有可用 **General Purchase Price**，狀態為 `無 General Purchase Price`。

狀態判定優先序固定為：

1. 沒有 target price 時，狀態為 `未設定目標價`。
2. 沒有 **General Purchase Price** 時，狀態為 `無 General Purchase Price`。
3. **General Purchase Price** 小於或等於 target price 時，狀態為 `達標`。
4. 其他狀態為 `未達標`。

PS Plus 價格不會讓 **Watched Product** 達標，即使 plus 價低於 target price。

`FREE` 不屬於 **General Purchase Price**，因此不會以 0 元讓 **Watched Product** 達標。第一版把 `FREE` 顯示為 `無 General Purchase Price`，避免把免費商品、trial、demo 或非付費內容誤判成付費 **Product** 降價到 0 元。

## Product detail 頁行為

`/products/<product_id>/` 保持既有 URL，新增 Watchlist 區塊。

尚未建立 **Watched Product**：

- 顯示 target price 表單。
- 提交有效 target price 後建立 `WatchedProduct`。
- target price 空白時仍建立 watchlist 記錄。

已建立 **Watched Product**：

- 顯示目前 target price。
- 再次提交會更新 target price。
- 顯示目前 watch 狀態。
- 提供移除 **Watched Product** action。

表單語意：

- 輸入單位是台幣元，例如 `590`。
- 後端存 `59000` cents。
- 空白 target price 存 `null`。
- 非空白 target price 必須是正整數台幣元；小數、`0` 與負數都是 invalid。
- 已建立 **Watched Product** 時提交空白 target price 會清空目標價並保留 **Watched Product**。
- invalid target price 顯示 validation error，不建立或更新 watchlist。
- 移除 **Watched Product** 只刪除 `WatchedProduct`，不刪 `StoreProduct` 或 `PriceSnapshot`。
- 建立、更新、清空與移除成功後使用 POST/Redirect/GET 回到同一個 Product detail 頁。
- invalid POST 不 redirect，直接以 HTTP 200 render 同一個 Product detail 頁並顯示錯誤；資料庫不得寫入。

## `/watchlist/` 頁面

`/watchlist/` 顯示所有 **Watched Product**。

`/watchlist/` 不用 **Catalog Visibility** 過濾 **Watched Product**。即使對應 **Product** 的 `is_visible = false`，仍應顯示在 watchlist，因為 **Catalog Visibility** 不代表使用者追蹤意圖消失。

每列顯示：

- **Product** 名稱。
- Product detail 頁連結。
- 最新 **General Purchase Price**。
- target price。
- watch 狀態。

狀態：

- `達標`
- `未達標`
- `無 General Purchase Price`
- `未設定目標價`

排序：

1. `達標`
2. `未達標`
3. `未設定目標價`
4. `無 General Purchase Price`
5. 同組內依 **Product** 名稱排序

沒有 **Watched Product** 時顯示 empty state，不回 404。

沒有 target price 的 **Watched Product** 仍然保留在 `/watchlist/`，用來表示「已決定追蹤，但尚未決定買入價」。這類項目不代表可購買決策，但使用者可以立刻補目標價，因此排序在 `無 General Purchase Price` 前面。

## 錯誤處理

- **Product** 不存在時，既有 detail 頁仍回 404。
- invalid target price 顯示表單錯誤，且不寫入資料庫。
- 沒有 snapshot 的 **Watched Product** 仍可顯示在 `/watchlist/`。
- 最新 snapshot 是 `PS_PLUS` 時顯示 `無 General Purchase Price`，不以 plus 價判定達標。
- 移除不存在的 **Watched Product** 視為 idempotent success，使用 POST/Redirect/GET 回到 Product detail 頁並顯示尚未建立 **Watched Product** 狀態。
- Watchlist POST 寫入行為只適合單人自架環境；若服務暴露到公網，需要先另行設計 authentication、authorization 與 CSRF 保護。

## 測試策略

測試集中在 model、query helper 與 view 行為。

至少涵蓋：

- `WatchedProduct` 與 `StoreProduct` 是一對一。
- 刪除 `StoreProduct` 會 cascade 刪除 `WatchedProduct`。
- `DISCOUNTED` 使用 `discounted_amount_cents` 判定達標。
- `PAID` 使用 `base_amount_cents` 判定達標。
- `PS_PLUS` 不算達標價格。
- 沒有 target price 時狀態為 `未設定目標價`。
- 沒有 **General Purchase Price** 時狀態為 `無 General Purchase Price`。
- `/watchlist/` empty state。
- `/watchlist/` 顯示 **Watched Product** 並依狀態排序。
- `/watchlist/` 不因 `StoreProduct.is_visible = false` 隱藏 **Watched Product**。
- detail 頁可新增 watchlist。
- detail 頁可更新 target price。
- detail 頁可移除 watchlist。
- detail 頁移除不存在的 **Watched Product** 視為成功，不回 404 或 500。
- detail 頁 watchlist POST 成功後 redirect 回同一 Product detail 頁。
- invalid target price 包含小數、`0` 與負數，會顯示錯誤且不寫入。
- invalid target price POST 回 HTTP 200，不 redirect。

驗證命令：

```bash
uv run pytest -q
```

## 成功標準

- 可以從 Product detail 頁建立 **Watched Product**。
- 可以從 Product detail 頁更新或清空 target price。
- 可以從 Product detail 頁移除 **Watched Product**。
- `/watchlist/` 顯示所有 **Watched Product**。
- `/watchlist/` 能區分達標、未達標、`無 General Purchase Price` 與未設定目標價。
- PS Plus 價格不會被算進 target price 達標判定。
- crawler、sync runner 與 scheduler 行為不變。
- `uv run pytest -q` 通過。
