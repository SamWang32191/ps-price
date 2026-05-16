# Docker Compose Self-Hosting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repo-local Docker Compose self-hosting path that runs the existing Django web UI and daily scheduler against a shared external SQLite data directory.

**Architecture:** Build one Python 3.12 application image with `uv.lock`-based runtime dependencies, then run it as two Compose services: `web` and `scheduler`. `web` owns migrations and health, while `scheduler` waits for `web` to become healthy before starting.

**Tech Stack:** Docker, Docker Compose, Python 3.12 slim image, uv, Django 5.2, SQLite, pytest.

---

## Scope Check

This plan implements one deployment subsystem: Docker Compose self-hosting. It does not implement admin actions, retry UI, auth, production web serving, TLS, PostgreSQL, or Docker image publishing.

## File Structure

- Modify `src/ps_price_site/settings.py`
  - Add tiny environment helpers for database path and allowed hosts.
  - Preserve existing development defaults when environment variables are unset.
- Modify `tests/test_django_setup.py`
  - Add focused tests for the new settings helpers.
- Create `Dockerfile`
  - Build a runtime image from `python:3.12-slim`.
  - Install `uv`, sync non-dev dependencies from `uv.lock`, and copy only runtime files.
- Create `.dockerignore`
  - Exclude local environments, git metadata, tests, docs, caches, worktrees, local SQLite, and live fixture output from Docker build context.
- Create `compose.yaml`
  - Define `web` and `scheduler`.
  - Bind-mount `/Users/samwang/dockercompose/ps-price/data` to `/data`.
  - Bind web only to `127.0.0.1:8000`.
  - Use `/` Dashboard endpoint as `web` healthcheck.
  - Make `scheduler` wait for `web` health.
- Modify `README.md`
  - Replace the "Docker Compose 尚未開始" milestone wording.
  - Add Docker Compose self-hosting usage and verification notes.

---

## Task 1: Add Minimal Deployment Settings

**Files:**
- Modify: `tests/test_django_setup.py`
- Modify: `src/ps_price_site/settings.py`

- [ ] **Step 1: Add failing tests for database path and allowed hosts helpers**

Append these tests to `tests/test_django_setup.py`:

```python
from ps_price_site import settings as project_settings


def test_database_name_defaults_to_repo_sqlite(monkeypatch) -> None:
    monkeypatch.delenv("PS_PRICE_DATABASE_PATH", raising=False)

    assert project_settings._database_name_from_env() == project_settings.BASE_DIR / "db.sqlite3"


def test_database_name_uses_environment_path(monkeypatch) -> None:
    monkeypatch.setenv("PS_PRICE_DATABASE_PATH", "/data/db.sqlite3")

    assert project_settings._database_name_from_env() == "/data/db.sqlite3"


def test_allowed_hosts_defaults_to_empty_list(monkeypatch) -> None:
    monkeypatch.delenv("PS_PRICE_ALLOWED_HOSTS", raising=False)

    assert project_settings._allowed_hosts_from_env() == []


def test_allowed_hosts_parses_comma_separated_environment(monkeypatch) -> None:
    monkeypatch.setenv("PS_PRICE_ALLOWED_HOSTS", "localhost, 127.0.0.1,,")

    assert project_settings._allowed_hosts_from_env() == ["localhost", "127.0.0.1"]
```

- [ ] **Step 2: Run focused tests and verify they fail**

Run:

```bash
uv run pytest tests/test_django_setup.py::test_database_name_defaults_to_repo_sqlite tests/test_django_setup.py::test_database_name_uses_environment_path tests/test_django_setup.py::test_allowed_hosts_defaults_to_empty_list tests/test_django_setup.py::test_allowed_hosts_parses_comma_separated_environment -q
```

Expected: FAIL with `AttributeError` because `_database_name_from_env` and `_allowed_hosts_from_env` do not exist.

- [ ] **Step 3: Implement settings helpers**

Replace `src/ps_price_site/settings.py` with:

```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def _database_name_from_env() -> Path | str:
    configured_path = os.environ.get("PS_PRICE_DATABASE_PATH", "").strip()
    if configured_path:
        return configured_path
    return BASE_DIR / "db.sqlite3"


def _allowed_hosts_from_env() -> list[str]:
    raw_hosts = os.environ.get("PS_PRICE_ALLOWED_HOSTS")
    if raw_hosts is None:
        return []
    return [host.strip() for host in raw_hosts.split(",") if host.strip()]


SECRET_KEY = "dev-only-ps-price"

DEBUG = True

ALLOWED_HOSTS = _allowed_hosts_from_env()

USE_TZ = True
TIME_ZONE = "Asia/Taipei"

ROOT_URLCONF = "ps_price_site.urls"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "ps_price_sync",
    "ps_price_web",
]

MIDDLEWARE: list[str] = []

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

STATIC_URL = "static/"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _database_name_from_env(),
    }
}
```

- [ ] **Step 4: Run focused settings tests and verify they pass**

Run:

```bash
uv run pytest tests/test_django_setup.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit settings change**

Run:

```bash
git add src/ps_price_site/settings.py tests/test_django_setup.py
git commit -m "feat: add deployment settings overrides"
```

---

## Task 2: Add Docker Runtime Image and Compose Services

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `compose.yaml`

- [ ] **Step 1: Create `.dockerignore`**

Create `.dockerignore` with:

```dockerignore
.git/
.github/
.pytest_cache/
.sisyphus/
.venv/
.worktrees/
__pycache__/
*.pyc
.DS_Store
.idea/
db.sqlite3
docs/
tests/
```

- [ ] **Step 2: Create `Dockerfile`**

Create `Dockerfile` with:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY manage.py ./
COPY src ./src
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]
```

- [ ] **Step 3: Create `compose.yaml`**

Create `compose.yaml` with:

```yaml
services:
  web:
    build:
      context: .
    environment:
      PS_PRICE_ALLOWED_HOSTS: localhost,127.0.0.1
      PS_PRICE_DATABASE_PATH: /data/db.sqlite3
    volumes:
      - /Users/samwang/dockercompose/ps-price/data:/data
    ports:
      - "127.0.0.1:8000:8000"
    command:
      - sh
      - -c
      - uv run python manage.py migrate --noinput && uv run python manage.py runserver 0.0.0.0:8000
    healthcheck:
      test:
        - CMD
        - uv
        - run
        - python
        - -c
        - "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=5).read()"
      interval: 10s
      timeout: 5s
      retries: 12
      start_period: 10s

  scheduler:
    build:
      context: .
    environment:
      PS_PRICE_ALLOWED_HOSTS: localhost,127.0.0.1
      PS_PRICE_DATABASE_PATH: /data/db.sqlite3
      PS_PRICE_SYNC_AT: "03:30"
      PS_PRICE_SYNC_TIMEZONE: Asia/Taipei
      PS_PRICE_SYNC_MODE: catalog-and-snapshot
      PS_PRICE_SYNC_MAX_PAGES: "500"
    volumes:
      - /Users/samwang/dockercompose/ps-price/data:/data
    depends_on:
      web:
        condition: service_healthy
    command:
      - uv
      - run
      - python
      - manage.py
      - run_daily_sync_scheduler
```

- [ ] **Step 4: Validate Compose syntax**

Run:

```bash
docker compose config
```

Expected: PASS. Output includes services named `web` and `scheduler`.

- [ ] **Step 5: Build the image**

Run:

```bash
docker compose build
```

Expected: PASS. Output completes without dependency resolution errors.

- [ ] **Step 6: Commit Docker and Compose files**

Run:

```bash
git add Dockerfile .dockerignore compose.yaml
git commit -m "feat: add docker compose deployment"
```

---

## Task 3: Document Docker Compose Self-Hosting

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update current milestone wording**

In `README.md`, replace this sentence fragment:

```markdown
目前 repo 已完成 crawler contract stabilization、Django data foundation 與第一版 daily sync scheduler，以及第一版 read-only Dashboard / 商品查詢介面；Docker Compose 尚未開始。
```

with:

```markdown
目前 repo 已完成 crawler contract stabilization、Django data foundation、第一版 daily sync scheduler、第一版 read-only Dashboard / 商品查詢介面，以及第一版 Docker Compose 自架部署。
```

- [ ] **Step 2: Replace next milestone wording**

In `README.md`, replace:

```markdown
下一個里程碑可聚焦 Docker Compose 自架部署，或再往 admin/手動操作與重跑錯誤功能前進。不要在這個交接點順手塞 auth、通知或 full detail backfill，這種「順手」通常就是專案管理的香蕉皮。
```

with:

```markdown
下一個里程碑可往 admin/手動操作與重跑錯誤功能前進。不要在這個交接點順手塞 auth、通知或 full detail backfill，這種「順手」通常就是專案管理的香蕉皮。
```

- [ ] **Step 3: Add Docker Compose usage section**

Insert this section after "Canonical setup and verification" and before "Django setup and sync usage":

````markdown
## Docker Compose self-hosting

第一版 Compose 部署檔放在 repo 內，會從同一個 image 啟動：

- `web`：跑 migration 後啟動 read-only Django UI。
- `scheduler`：等待 `web` healthcheck 通過後，跑每日同步 scheduler。

持久化 SQLite data 放在 repo 外：

```bash
mkdir -p /Users/samwang/dockercompose/ps-price/data
```

完整自架啟動：

```bash
docker compose up --build
```

UI 只綁 localhost：

- `http://127.0.0.1:8000/`

只想啟動 UI、不跑每日同步時：

```bash
docker compose up --build web
```

Compose 內使用 `/data/db.sqlite3`。如果 SQLite 無法建立或寫入，先檢查 `/Users/samwang/dockercompose/ps-price/data` 的 owner 與寫入權限。

必跑 smoke checks：

```bash
docker compose config
docker compose build
docker compose run --rm web uv run python -c "from django.conf import settings; print(settings.DATABASES['default']['NAME'])"
docker compose run --rm web uv run python manage.py migrate --noinput
docker compose run --rm web uv run python manage.py migrate --check
docker compose up -d --build web
```

確認 `http://127.0.0.1:8000/` 回應後可關閉：

```bash
docker compose down
```

完整 `docker compose up --build` 會同時啟動 scheduler；如果接近排程時間，可能觸發 live PlayStation Store sync。live sync 不屬於 CI requirement。
````

- [ ] **Step 4: Run README-focused test**

Run:

```bash
uv run pytest tests/test_django_setup.py::test_readme_mentions_django_sync_commands -q
```

Expected: PASS.

- [ ] **Step 5: Commit README update**

Run:

```bash
git add README.md
git commit -m "docs: add docker compose self-hosting usage"
```

---

## Task 4: Verify Deployment Path End-to-End

**Files:**
- Verify: `src/ps_price_site/settings.py`
- Verify: `Dockerfile`
- Verify: `compose.yaml`
- Verify: `README.md`

- [ ] **Step 1: Run full offline Python test suite**

Run:

```bash
uv run pytest -v
```

Expected: PASS. No test should require live PlayStation Store access.

- [ ] **Step 2: Ensure host data directory exists**

Run:

```bash
mkdir -p /Users/samwang/dockercompose/ps-price/data
```

Expected: command exits successfully.

- [ ] **Step 3: Validate Compose config**

Run:

```bash
docker compose config
```

Expected: PASS. Output contains `web`, `scheduler`, `/Users/samwang/dockercompose/ps-price/data:/data`, and `127.0.0.1:8000:8000`.

- [ ] **Step 4: Build Compose image**

Run:

```bash
docker compose build
```

Expected: PASS. Build completes with `uv sync --frozen --no-dev`.

- [ ] **Step 5: Verify Django can see the Compose database path**

Run:

```bash
docker compose run --rm web uv run python -c "from django.conf import settings; print(settings.DATABASES['default']['NAME'])"
```

Expected output:

```text
/data/db.sqlite3
```

- [ ] **Step 6: Run migrations and verify no pending migrations remain**

Run:

```bash
docker compose run --rm web uv run python manage.py migrate --noinput
docker compose run --rm web uv run python manage.py migrate --check
```

Expected: PASS. The first command applies migrations to `/data/db.sqlite3`; the second command exits with status 0 because no migrations remain pending.

- [ ] **Step 7: Start only the web service**

Run:

```bash
docker compose up -d --build web
```

Expected: PASS. Only `web` starts; `scheduler` does not start.

- [ ] **Step 8: Check the local UI**

Run:

```bash
curl -fsS http://127.0.0.1:8000/ >/dev/null
```

Expected: PASS. The command exits with status 0.

- [ ] **Step 9: Shut down Compose services**

Run:

```bash
docker compose down
```

Expected: PASS.

- [ ] **Step 10: Confirm git state**

Run:

```bash
git status --short
```

Expected: no output.
