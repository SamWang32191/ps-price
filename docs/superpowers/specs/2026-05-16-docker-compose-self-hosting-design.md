# Docker Compose 自架部署設計

日期：2026-05-16

## 目標

替 PlayStation Store 台灣價格追蹤器加入第一版 Docker Compose 自架部署路徑。

部署必須從同一個 repo 跑既有 Django read-only UI 與既有 daily scheduler，同時把持久化 SQLite 資料放在 git working tree 外。

## 現況

目前 repo 已有：

- Django settings、models、migrations 與 read-only web pages。
- `sync_ps_store` management command，負責 catalog 與 snapshot 同步。
- `run_daily_sync_scheduler` management command，負責單一 daily scheduler process。
- README 中的本機 `uv` 開發流程與 scheduler 環境變數說明。

目前 repo 尚未有 Docker 或 Compose 部署檔。

## 已確認方向

使用一個 app image 與兩個 Compose services：

- `web`
- `scheduler`

部署檔放在 repo 內。持久化 runtime data 放在 repo 外：

```text
/Users/samwang/dockercompose/ps-price/data
```

容器內掛載位置：

```text
/data
```

Compose 使用 host bind mount，不使用 named volume。正式流程要求使用者先建立 host data directory，不依賴 Docker 自動建立 bind mount 目錄。

Compose 內 SQLite database path：

```text
/data/db.sqlite3
```

## 架構

新增這些 repo 檔案：

- `Dockerfile`
- `.dockerignore`
- `compose.yaml`

`Dockerfile` build 一個可重用 application image。image 會安裝專案 dependencies 並包含 Django project source。它不在同一個容器中跑多個長駐 process。base image 固定 Python 3.12 minor version，例如 `python:3.12-slim`，不釘死 patch version。

image dependency installation 使用 repo 既有 `uv.lock`，以 locked install 建立 runtime environment，不安裝 dev dependencies。這讓 container dependency path 與 README / CI 的 `uv` 路徑保持一致，並避免部署時依賴漂移。

runtime image 只複製執行需要的檔案：`pyproject.toml`、`uv.lock`、`manage.py` 與 `src/`。`docs/`、`tests/`、`.git/`、`.venv/`、`.pytest_cache/`、`.sisyphus/`、`.worktrees/`、本機 `db.sqlite3` 與其他暫存輸出不放進 image。

Compose runtime commands 沿用 repo canonical convention，使用 `uv run python manage.py ...` 執行 Django management commands。

`compose.yaml` 定義：

- `web`：每次 container start 都先執行 `uv run python manage.py migrate --noinput`，成功後才啟動 Django development server，server 綁在容器內 `0.0.0.0:8000`。
- `scheduler`：等 `web` healthcheck 通過後，執行 `uv run python manage.py run_daily_sync_scheduler`。

`docker compose up --build` 預設同時啟動 `web` 與 `scheduler`。如果只想啟動 UI，不跑每日同步，可明確執行 `docker compose up web`。

`web` healthcheck 使用既有 `/` Dashboard endpoint，期待 HTTP 200。healthcheck 使用 Python 標準庫發 HTTP request，不為此額外安裝 `curl` 或 `wget`。這比新增專用 `/health/` endpoint 更能驗證第一版部署真正需要的路徑：Django process、URL routing、templates 與 SQLite schema 都可用。

host port mapping 只綁 localhost：

```yaml
127.0.0.1:8000:8000
```

這讓第一版部署維持在同機自用範圍。

## 設定

Django settings 只做最小部署化。

新增 `PS_PRICE_DATABASE_PATH`：

- 未設定時，Django 維持目前 development default：`BASE_DIR / "db.sqlite3"`。
- Compose 內設定為 `/data/db.sqlite3`。

新增 `PS_PRICE_ALLOWED_HOSTS`：

- 未設定時，維持目前本機開發行為：`ALLOWED_HOSTS = []`。
- Compose 內設定為 `localhost,127.0.0.1`。
- Django 將逗號分隔字串解析成 `ALLOWED_HOSTS` list。

本里程碑不把 settings 改成完整 production settings model。`DEBUG`、`SECRET_KEY`、static collection、reverse proxy、TLS、authentication 與 admin hardening 都不在範圍內。

## Runtime Flow

1. 使用者先建立 host data directory：

   ```bash
   mkdir -p /Users/samwang/dockercompose/ps-price/data
   ```

2. 使用者執行：

   ```bash
   docker compose up --build
   ```

3. Compose build 共用 app image。
4. `web` 對 `/data/db.sqlite3` 執行 `uv run python manage.py migrate --noinput`，接著在容器 port `8000` 啟動 Django。
5. `web` healthcheck 對 `/` 取得 HTTP 200 後才通過。
6. UI 可透過 `http://127.0.0.1:8000/` 使用。
7. `scheduler` 透過 Compose `depends_on` 等 `web` healthcheck 通過後，使用既有 scheduler command 跑單一 daily scheduler loop。
8. 第一次部署時，`scheduler` 不應早於 `web` migration 接觸 `/data/db.sqlite3`。
9. `web` 與 `scheduler` 透過 `/data` mount 共用同一個 SQLite database file。

## Scheduler 環境變數

Compose 應帶出既有 scheduler 環境變數與第一版預設值：

- `PS_PRICE_SYNC_AT=03:30`
- `PS_PRICE_SYNC_TIMEZONE=Asia/Taipei`
- `PS_PRICE_SYNC_MODE=catalog-and-snapshot`
- `PS_PRICE_SYNC_MAX_PAGES=500`

只能跑一個 scheduler service。既有 scheduler 不實作跨 process distributed lock。

## 錯誤處理

以下情境應讓 container startup 明確失敗：

- build 階段 dependencies 安裝失敗。
- migrations 失敗。
- Django settings 無效。
- 掛載的 data path 不可寫。

第一版 container 不新增 non-root user 或 UID/GID mapping。若 host data directory 權限導致 SQLite 無法建立或寫入，README 應提示先檢查 `/Users/samwang/dockercompose/ps-price/data` 的 owner 與寫入權限。

scheduler 維持目前行為：sync 失敗時記錄 log，然後等下一次排程。此里程碑不新增 retry queue。

SQLite write contention 是第一版自用部署可接受的取捨。此部署只綁 localhost 且低流量；如果未來 web read 與 scheduler write 產生 lock 問題，另開針對性里程碑處理。

## 驗證

離線驗證：

- 新增 `PS_PRICE_DATABASE_PATH` settings tests。
- 新增 `PS_PRICE_ALLOWED_HOSTS` settings tests。
- 跑完整既有測試：

  ```bash
  uv run pytest -v
  ```

Compose 必跑 smoke 驗證：

- `docker compose config` 成功。
- `docker compose build` 成功。
- 透過 Compose 執行的 Django command 可以存取設定後的 database path。
- `docker compose up -d --build web` 能啟動 `web`，且不啟動 `scheduler`。
- `web` healthcheck 對 `/` 取得 HTTP 200。
- `http://127.0.0.1:8000/` 回傳 Django UI。

完整部署 smoke 可手動執行 `docker compose up --build`，確認 `web` 與 `scheduler` 都能啟動，且 `scheduler` 在 `web` healthcheck 通過後才啟動。此步驟可能接近排程時間而觸發 live PlayStation Store sync，因此不作為必跑驗證，也不做成 CI requirement。

## 非目標

本里程碑不包含：

- production web server，例如 gunicorn 或 uvicorn。
- nginx、TLS 或 reverse proxy setup。
- non-root container user 或 UID/GID mapping。
- authentication。
- Django admin customization。
- manual sync buttons。
- retry queue 或 SyncError rerun UI。
- 跨多個 scheduler process 的 distributed locking。
- PostgreSQL 或其他 database。
- Docker image publishing。

## 成功標準

- 部署檔放在 repo 內。
- `docker compose up --build` 可以在本機跑起 app。
- web UI 只綁 `127.0.0.1:8000`。
- SQLite data 持久化在 `/Users/samwang/dockercompose/ps-price/data`。
- `web` 與 `scheduler` 使用同一個 database file。
- 既有非 Docker 開發流程仍使用預設 repo root `db.sqlite3` 並可正常運作。
- 既有測試仍通過。
