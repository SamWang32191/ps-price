# ps-price

自架的 PlayStation Store 台灣價格追蹤器。

## 目前里程碑

第一個里程碑是 crawler spike，用來驗證 PlayStation Store 台灣 SSR 頁面是否暴露足夠的嵌入式 JSON，可解析出：

- 型錄頁總數與 concept ID
- concept / product 名稱
- 平台與 product 類別欄位
- 可見的公開價格欄位

## Spike 指令

本 repo 以 `uv` 作為本機與 CI 共用的可重現驗證路徑。Task 1 的基準只跑離線測試，不執行即時 PlayStation Store 抓取或 fixture capture。

```bash
uv sync --extra dev
uv run pytest -v
```

## 資料來源備註

crawler spike 從 PlayStation Store 台灣 SSR 頁面開始：

- 型錄：`/zh-hant-tw/category/28c9c2b2-cecc-415c-9a08-482a605cb104/{page}`
- concept 詳情：`/zh-hant-tw/concept/{conceptId}`

parser 會讀取嵌入的 `__NEXT_DATA__` 與 `env:*` JSON script payload。這是 PlayStation Store 網站的非公開實作細節，因此 parser 失效會被視為預期內的維護事件。
