# PS Price Crawler Contract Stabilization

## TL;DR
> **Summary**: Stabilize the PlayStation Store Taiwan crawler spike into a dependable adapter contract before starting Django. This plan captures missing price edge cases, defines normalized product/price semantics, hardens parsers/CLI, and adds reproducible offline verification.
> **Deliverables**:
> - `uv`-based verification path and CI that runs deterministic offline tests
> - Normalized crawler product/price contract with explicit nullable/error semantics
> - Real fixture workflow for free, paid, discounted, PS Plus, unavailable/not-purchasable cases
> - Parser tests and CLI reporting for catalog/detail strategy decisions
> - Updated documentation handoff for the later Django + SQLite data foundation milestone
> **Effort**: Medium
> **Parallel**: YES - 5 waves
> **Critical Path**: Task 1 → Task 3 → Task 4 → Task 5 → Task 7 → Task 8

## Context
### Original Request
使用者要求：「擬定後續的plan」。前一輪 repo 健檢結論是：目前 repo 是 crawler spike，不應直接開 Django。

### Interview Summary
- 目前 repo 在 `main`，工作區乾淨。
- README 指出現階段是 crawler spike，CLI 指令為 `ps-price-crawler catalog` 與 `ps-price-crawler concept`。
- `docs/spikes/ps-store-crawler-spike.md` 已確認 catalog/concept 可解析，但明列缺口：discounted paid、PS Plus、unavailable/non-purchasable fixtures，以及 catalog price vs concept detail fetch strategy。
- `docs/superpowers/specs/2026-04-27-ps-low-price-design.md` 的 v1 是 Django + SQLite + Docker-first self-use site，但此 plan 明確不做 Django。
- 本環境 `python` 不存在、`python3` 沒有 pytest；`uv` 存在，因此驗證路徑採 `uv run ...`。

### Metis Review (gaps addressed)
- Metis 指出最大風險是提早開 Django，導致不穩定 crawler 資料被 premature schema freeze。
- Metis 要求分開 deterministic offline tests 與 live PS Store smoke/capture commands。
- Metis 要求定義 normalized product/price contract、nullable/error semantics、catalog-vs-concept strategy、fixture refresh workflow。
- Metis 要求若 edge-case concept IDs 未知，先以 research task 產出具體 fixture targets，再讓 implementation tasks 依賴該 artifact。

## Work Objectives
### Core Objective
把 PlayStation Store Taiwan crawler spike 升級成可供後續 Django ingestion 使用的穩定資料契約。

### Deliverables
- Stable source/test contract under `src/ps_price_crawler/` and `tests/`.
- Real fixture target report under `.sisyphus/evidence/task-3-fixture-targets.json`.
- Committed deterministic fixture set under `tests/fixtures/ps_store/`; raw HTML fixtures may be committed only when each raw HTML file is `<= 2 MiB` and the total `tests/fixtures/ps_store/` directory is `<= 10 MiB`. If either limit is exceeded, commit normalized JSON fixtures plus SHA-256/size metadata and keep raw HTML only under ignored `tests/fixtures/live/` with documented rationale.
- CI workflow under `.github/workflows/ci.yml` running offline tests only.
- Updated `README.md` and `docs/spikes/ps-store-crawler-spike.md` documenting source strategy and next Django handoff.

### Definition of Done (verifiable conditions with commands)
- `uv run pytest -v` passes without network access.
- `uv run ps-price-crawler catalog --pages 2 --format json` exits 0 and prints JSON with catalog summary and normalized price states.
- `uv run ps-price-crawler concept 223118 --format json` exits 0 and prints JSON containing concept `223118` and a `FREE` normalized state.
- `.github/workflows/ci.yml` exists and does not run live PlayStation Store commands.
- `docs/spikes/ps-store-crawler-spike.md` documents the selected snapshot source strategy: catalog-first, concept-detail fallback.

### Must Have
- Explicit price states: `FREE`, `PAID`, `DISCOUNTED`, `PS_PLUS`, `UNAVAILABLE`, `NOT_PURCHASABLE`, `UNKNOWN`.
- `None` semantics documented: absent raw field vs parser failure vs intentionally unavailable must not collapse into one mystery soup.
- Fixture coverage for free, paid full-price, discounted paid, PS Plus, unavailable/not-purchasable, malformed `__NEXT_DATA__`, malformed/missing `env:*` JSON.
- CI must be offline and deterministic.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No Django app scaffold.
- No SQLite models or migrations.
- No scheduler, Docker Compose, dashboard UI, auth, notifications, cloud deployment, or full catalog detail backfill.
- No live PS Store command in required CI.
- No vague acceptance criteria such as “verify manually” or “improve parser”. If a task says that, roast it and rewrite it; it is wearing a fake mustache.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: TDD/tests-after hybrid with `pytest` via `uv run pytest`; parser/contract changes start from failing tests, docs/CI changes are tests-after.
- QA policy: Every task has agent-executed scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`.
- Offline commands are mandatory; live commands are explicit smoke/capture steps and must write evidence separately.
- CI policy: CI runs `uv run pytest -v` only; no live network crawler commands.

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: Task 1 tooling baseline, Task 2 normalized contract design/tests, Task 3 fixture target discovery.
Wave 2: Task 4 fixture capture, Task 6 source strategy decision implementation.
Wave 3: Task 5 parser hardening.
Wave 4: Task 7 CLI JSON/reporting.
Wave 5: Task 8 docs/handoff and final verification readiness.

### Dependency Matrix (full, all tasks)
| Task | Depends On | Blocks |
|---|---|---|
| 1. Reproducible tooling and CI baseline | none | 3, 4, 5, 7, 8 |
| 2. Normalized price/product contract | none | 5, 6, 7, 8 |
| 3. Live fixture target discovery | 1 | 4, 5, 7, 8 |
| 4. Deterministic fixture set | 1, 3 | 5, 7, 8 |
| 5. Parser hardening against fixture states | 2, 4 | 7, 8 |
| 6. Snapshot source strategy | 2, 3 | 7, 8 |
| 7. CLI JSON/reporting contract | 5, 6 | 8 |
| 8. Documentation and Django handoff | 1, 2, 3, 4, 5, 6, 7 | Final Verification Wave |

### Agent Dispatch Summary (wave → task count → categories)
| Wave | Task Count | Categories |
|---|---:|---|
| 1 | 3 | `unspecified-high`, `quick`, `deep` |
| 2 | 2 | `unspecified-high`, `deep` |
| 3 | 1 | `unspecified-high` |
| 4 | 1 | `unspecified-high` |
| 5 | 1 | `writing` |

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Reproducible tooling and offline CI baseline

  **What to do**: Establish `uv` as the canonical local/CI execution path because this environment has no `python` command and `python3` lacks pytest. Generate/commit `uv.lock`, add `.github/workflows/ci.yml`, and update README commands so humans and CI both run the same offline verification path.
  **Must NOT do**: Do not add ruff, mypy, pre-commit, Docker, or live crawler commands to CI in this task. Quality-tooling sprawl at this point would be a clown car with YAML doors.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: touches project tooling, CI, and docs with repo-wide impact.
  - Skills: [`superpowers/test-driven-development`] - Use only for verification discipline; no production parser change here.
  - Omitted: [`frontend-ui-ux`] - No UI work.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 3, 4, 5, 7, 8 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Project config: `pyproject.toml:1-30` - current package metadata, runtime deps, dev deps, pytest config.
  - README commands: `README.md:14-23` - currently uses `python`/`pytest`; update to `uv` commands.
  - Environment finding: local `python` is absent, `python3` has no pytest, `/opt/homebrew/bin/uv` exists.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv lock` exits `0` and creates/updates `uv.lock`.
  - [ ] `uv run pytest -v` exits `0` and runs only offline tests.
  - [ ] `.github/workflows/ci.yml` exists and contains `astral-sh/setup-uv`, `uv sync --extra dev`, and `uv run pytest -v`.
  - [ ] `.github/workflows/ci.yml` does not contain `ps-price-crawler catalog`, `ps-price-crawler concept`, `store.playstation.com`, or `--save-fixtures`.
  - [ ] README spike setup commands use `uv sync --extra dev` and `uv run pytest -v` instead of bare `python`, `pip`, or `pytest`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Offline local verification works with uv
    Tool: Bash
    Steps: Run `uv sync --extra dev && uv run pytest -v | tee .sisyphus/evidence/task-1-uv-pytest.txt` from repo root.
    Expected: Command exits 0; evidence file contains pytest session output and all collected tests pass.
    Evidence: .sisyphus/evidence/task-1-uv-pytest.txt

  Scenario: CI remains offline-only
    Tool: Bash
    Steps: Run `python3 - <<'PY'\nfrom pathlib import Path\nci=Path('.github/workflows/ci.yml').read_text()\nfor forbidden in ['ps-price-crawler catalog','ps-price-crawler concept','store.playstation.com','--save-fixtures']:\n    assert forbidden not in ci, forbidden\nassert 'uv run pytest -v' in ci\nPY`
    Expected: Command exits 0; no forbidden live crawler command appears in CI.
    Evidence: .sisyphus/evidence/task-1-ci-offline.txt
  ```

  **Commit**: YES | Message: `ci: add uv pytest workflow` | Files: [`uv.lock`, `.github/workflows/ci.yml`, `README.md`]

- [x] 2. Normalized product/price contract

  **What to do**: Add a normalized contract layer that converts raw `PriceInfo` strings into explicit price states and typed money values while preserving raw display text. Create `src/ps_price_crawler/price_contract.py` and `tests/test_price_contract.py`. The contract must define `PriceState` values exactly: `FREE`, `PAID`, `DISCOUNTED`, `PS_PLUS`, `UNAVAILABLE`, `NOT_PURCHASABLE`, `UNKNOWN`. It must define `NormalizedPrice` with fields: `state`, `currency`, `base_amount_cents`, `discounted_amount_cents`, `plus_amount_cents`, `base_display`, `discounted_display`, `discount_text`, `service_branding`, `upsell_text`, `source`, `raw_missing_reason`.
  **Must NOT do**: Do not wire this into catalog/product parsers yet; that is Task 5. Do not discard raw display strings because localized price text is source evidence, not decorative parsley.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: focused new module and tests.
  - Skills: [`superpowers/test-driven-development`] - Contract should be test-first.
  - Omitted: [`superpowers/systematic-debugging`] - No bug reproduction yet.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5, 6, 7, 8 | Blocked By: none

  **References**:
  - Raw price model: `src/ps_price_crawler/models.py:6-15` - existing `PriceInfo` fields.
  - Catalog parser raw mapping: `src/ps_price_crawler/catalog.py:107-119` - current `_price_info` mapping.
  - Product free inference: `src/ps_price_crawler/product.py:51-63` - current `DOWNLOAD` CTA fallback.
  - Tests style: `tests/test_catalog.py:74-94`, `tests/test_product.py:340-404` - direct pytest assertions and explicit failure cases.

  **Acceptance Criteria**:
  - [ ] `tests/test_price_contract.py` covers TWD parsing: `NT$1,690` -> `169000`, `NT$1,990` -> `199000`, `免費` -> free state with `0` discounted amount.
  - [ ] `tests/test_price_contract.py` covers discounted paid state when `basePrice != discountedPrice` or `discountText` is present.
  - [ ] `tests/test_price_contract.py` covers PS Plus state when `is_exclusive` or `is_tied_to_subscription` is true, or service branding/upsell text indicates Plus.
  - [ ] `tests/test_price_contract.py` covers `UNKNOWN` when raw price is missing and `raw_missing_reason` is set.
  - [ ] `uv run pytest tests/test_price_contract.py -v` exits `0`.

  **QA Scenarios**:
  ```
  Scenario: Known localized TWD prices normalize deterministically
    Tool: Bash
    Steps: Run `uv run pytest tests/test_price_contract.py -v | tee .sisyphus/evidence/task-2-price-contract.txt`.
    Expected: Exit 0; test output includes cases for FREE, PAID, DISCOUNTED, PS_PLUS, UNKNOWN.
    Evidence: .sisyphus/evidence/task-2-price-contract.txt

  Scenario: Ambiguous missing price does not masquerade as free
    Tool: Bash
    Steps: Run `uv run pytest tests/test_price_contract.py::test_missing_raw_price_returns_unknown_with_reason -v | tee .sisyphus/evidence/task-2-missing-price.txt`.
    Expected: Exit 0; assertion confirms state `UNKNOWN` and non-empty `raw_missing_reason`.
    Evidence: .sisyphus/evidence/task-2-missing-price.txt
  ```

  **Commit**: YES | Message: `feat(crawler): define normalized price contract` | Files: [`src/ps_price_crawler/price_contract.py`, `tests/test_price_contract.py`]

- [x] 3. Live fixture target discovery command and evidence

  **What to do**: Add a bounded live discovery command that scans catalog pages for concrete concept IDs covering required price states. Extend `src/ps_price_crawler/cli.py` with subcommand `fixture-targets`:
  `uv run ps-price-crawler fixture-targets --pages 80 --output .sisyphus/evidence/task-3-fixture-targets.json`.
  The command must fetch catalog pages conservatively through `PlayStationStoreClient`, parse `CatalogItem.price`, and output JSON with keys: `free`, `paid_full_price`, `discounted_paid`, `ps_plus_candidate`, `missing_or_unavailable_candidate`. Each key must contain `concept_id`, `name`, `source_url`, `price_fields`, and `reason`. Use concept `223118` as free fallback only if discovery does not find another free item.
  **Must NOT do**: Do not fetch every concept detail page in this task. Do not increase concurrency. Do not treat missing category as success; if pages 1-80 cannot find a required category, output `null` for that key and exit with code `2` so the blocker is loud instead of politely useless.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: live source behavior and bounded discovery need careful failure semantics.
  - Skills: [`superpowers/systematic-debugging`] - Use if live source shape differs from existing parser assumptions.
  - Omitted: [`superpowers/test-driven-development`] - This task includes tests, but the main risk is live discovery behavior.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 4, 5, 7, 8 | Blocked By: 1

  **References**:
  - CLI structure: `src/ps_price_crawler/cli.py:11-31` - add subcommand here.
  - Catalog runner: `src/ps_price_crawler/cli.py:34-49` - reuse page iteration and output patterns.
  - Client delay: `src/ps_price_crawler/client.py:14-49` - keep conservative delay behavior.
  - Known free concept: `docs/spikes/ps-store-crawler-spike.md:24-31` - `223118` Roblox free sample.
  - Known gaps: `docs/spikes/ps-store-crawler-spike.md:33-38` - target categories.

  **Acceptance Criteria**:
  - [ ] `tests/test_cli_fixture_targets.py` covers JSON output classification from synthetic `CatalogPage` data.
  - [ ] `uv run pytest tests/test_cli_fixture_targets.py -v` exits `0`.
  - [ ] `uv run ps-price-crawler fixture-targets --pages 80 --output .sisyphus/evidence/task-3-fixture-targets.json` exits `0` only when all required keys are non-null.
  - [ ] `.sisyphus/evidence/task-3-fixture-targets.json` contains concrete concept IDs for `free`, `paid_full_price`, `discounted_paid`, `ps_plus_candidate`, and `missing_or_unavailable_candidate`.
  - [ ] If the live command exits `2`, stop execution and record the JSON plus stderr in `.sisyphus/evidence/task-3-fixture-targets-blocked.txt`; do not proceed to Task 4 until a follow-up plan resolves targets.

  **QA Scenarios**:
  ```
  Scenario: Synthetic candidate classification is deterministic
    Tool: Bash
    Steps: Run `uv run pytest tests/test_cli_fixture_targets.py -v | tee .sisyphus/evidence/task-3-classification-tests.txt`.
    Expected: Exit 0; synthetic catalog data classifies free, paid, discounted, PS Plus, and missing/unavailable candidates.
    Evidence: .sisyphus/evidence/task-3-classification-tests.txt

  Scenario: Live bounded discovery produces concrete target IDs
    Tool: Bash
    Steps: Run `uv run ps-price-crawler fixture-targets --pages 80 --output .sisyphus/evidence/task-3-fixture-targets.json 2>&1 | tee .sisyphus/evidence/task-3-live-discovery.txt`.
    Expected: Exit 0; JSON file has non-null `concept_id` values for all required keys. Exit 2 is a blocker, not a pass.
    Evidence: .sisyphus/evidence/task-3-live-discovery.txt and .sisyphus/evidence/task-3-fixture-targets.json
  ```

  **Commit**: YES | Message: `feat(crawler): discover fixture target concepts` | Files: [`src/ps_price_crawler/cli.py`, `tests/test_cli_fixture_targets.py`]

- [x] 4. Deterministic fixture set for required price states

  **What to do**: Use `.sisyphus/evidence/task-3-fixture-targets.json` to capture concept/detail fixtures for the required states, then create deterministic committed fixtures under `tests/fixtures/ps_store/`. For each required key, save normalized expected output as `tests/fixtures/ps_store/concept_<state>_<concept_id>.json`. Save raw HTML as `tests/fixtures/ps_store/concept_<state>_<concept_id>.html` only if that individual file is `<= 2 MiB` and the whole `tests/fixtures/ps_store/` directory remains `<= 10 MiB`; otherwise keep raw HTML under ignored `tests/fixtures/live/` and include `raw_html_sha256`, `raw_html_size_bytes`, and `raw_html_omitted_reason` in the committed JSON fixture. Add `tests/test_fixture_contract.py` that loads every committed fixture and asserts normalized state, concept ID, product ID behavior, and no parser traceback.
  **Must NOT do**: Do not commit `tests/fixtures/live/`; it is ignored for a reason. Do not silently skip large HTML; if raw HTML exceeds the explicit size limits, write the normalized JSON fixture and document the raw-file exclusion in `docs/spikes/ps-store-crawler-spike.md`.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: combines live capture, fixture curation, and deterministic tests.
  - Skills: [`superpowers/test-driven-development`] - Fixture tests define the contract before parser changes in Task 5.
  - Omitted: [`frontend-ui-ux`] - No browser/UI work.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 5, 7, 8 | Blocked By: 1, 3

  **References**:
  - Ignored live fixtures: `.gitignore:5` - `tests/fixtures/live/` must stay uncommitted.
  - Existing concept CLI: `src/ps_price_crawler/cli.py:51-62` - capture detail pages.
  - Existing product parser: `src/ps_price_crawler/product.py:10-48` - fixture tests should exercise this entry point.
  - Known target categories: `docs/spikes/ps-store-crawler-spike.md:33-38`.

  **Acceptance Criteria**:
  - [ ] `tests/fixtures/ps_store/` exists with committed deterministic fixture files for free, paid full-price, discounted paid, PS Plus, and unavailable/not-purchasable or documented normalized fallback.
  - [ ] `python3 - <<'PY'\nfrom pathlib import Path\nfiles=list(Path('tests/fixtures/ps_store').glob('*.html'))\nassert all(p.stat().st_size <= 2*1024*1024 for p in files)\ntotal=sum(p.stat().st_size for p in Path('tests/fixtures/ps_store').rglob('*') if p.is_file())\nassert total <= 10*1024*1024, total\nPY` exits `0`.
  - [ ] `tests/test_fixture_contract.py` reads all fixture JSON files and asserts `PriceState` values exactly.
  - [ ] `uv run pytest tests/test_fixture_contract.py -v` exits `0` without network.
  - [ ] `git status --short --ignored` shows `tests/fixtures/live/` ignored and no ignored live HTML staged.

  **QA Scenarios**:
  ```
  Scenario: Offline fixture contract validates every committed state
    Tool: Bash
    Steps: Run `uv run pytest tests/test_fixture_contract.py -v | tee .sisyphus/evidence/task-4-fixture-contract.txt`.
    Expected: Exit 0; tests cover free, paid_full_price, discounted_paid, ps_plus_candidate, missing_or_unavailable_candidate.
    Evidence: .sisyphus/evidence/task-4-fixture-contract.txt

  Scenario: Ignored live captures are not staged
    Tool: Bash
    Steps: Run `git status --short --ignored | tee .sisyphus/evidence/task-4-git-status-ignored.txt`.
    Expected: Output may show ignored `tests/fixtures/live/`, but `git status --short` has no staged `tests/fixtures/live/` files.
    Evidence: .sisyphus/evidence/task-4-git-status-ignored.txt
  ```

  **Commit**: YES | Message: `test(crawler): add deterministic price fixtures` | Files: [`tests/fixtures/ps_store/`, `tests/test_fixture_contract.py`, `docs/spikes/ps-store-crawler-spike.md` if raw exclusions are documented]

- [x] 5. Parser hardening and normalized integration

  **What to do**: Wire `price_contract.py` into catalog and product parsing so parser outputs can produce normalized price states from real fixtures. Add typed parse errors in `src/ps_price_crawler/errors.py`: `CrawlerParseError`, `MissingEmbeddedStateError`, `MissingRequiredFieldError`, `AmbiguousCacheEntryError`. Replace random `ValueError` confetti in `next_data.py`, `catalog.py`, and `product.py` with these typed errors while preserving message specificity. Add tests for malformed `__NEXT_DATA__`, malformed/missing `env:*`, duplicate catalog entries, product price missing on detail but present in catalog, and `DOWNLOAD` CTA free inference.
  **Must NOT do**: Do not change public CLI behavior except where tests require clearer error propagation. Do not invent database fields. Parser hardening is not an invitation to sneak in an ORM wearing a trench coat.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: modifies core parsing behavior with broad test impact.
  - Skills: [`superpowers/test-driven-development`, `superpowers/systematic-debugging`] - Test-first parser hardening and disciplined diagnosis for fixture regressions.
  - Omitted: [`frontend-ui-ux`] - No UI.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 7, 8 | Blocked By: 2, 4

  **References**:
  - JSON extraction: `src/ps_price_crawler/next_data.py:19-49` - replace generic JSON/object errors with typed parse errors.
  - Catalog parser required fields: `src/ps_price_crawler/catalog.py:10-34`, `src/ps_price_crawler/catalog.py:122-143` - typed missing-field errors.
  - Product parser cache/detail: `src/ps_price_crawler/product.py:10-48`, `src/ps_price_crawler/product.py:90-132`, `src/ps_price_crawler/product.py:145-169` - typed cache ambiguity and required-field errors.
  - Existing edge tests: `tests/test_product.py:66-215`, `tests/test_product.py:340-404` - preserve these behaviors with updated exception classes/messages.
  - New contract: `src/ps_price_crawler/price_contract.py` from Task 2.
  - Deterministic fixtures: `tests/fixtures/ps_store/` from Task 4.

  **Acceptance Criteria**:
  - [ ] `tests/test_next_data.py` includes malformed JSON and non-object JSON cases asserting typed errors.
  - [ ] `tests/test_catalog.py` includes duplicate concept/product handling and missing price normalization cases.
  - [ ] `tests/test_product.py` existing failure tests still pass with typed errors containing the same field names in messages.
  - [ ] `tests/test_fixture_contract.py` passes and asserts normalized state for each deterministic fixture.
  - [ ] `uv run pytest tests/test_next_data.py tests/test_catalog.py tests/test_product.py tests/test_fixture_contract.py -v` exits `0`.

  **QA Scenarios**:
  ```
  Scenario: Parser test suite passes with typed errors
    Tool: Bash
    Steps: Run `uv run pytest tests/test_next_data.py tests/test_catalog.py tests/test_product.py tests/test_fixture_contract.py -v | tee .sisyphus/evidence/task-5-parser-suite.txt`.
    Expected: Exit 0; typed parse errors are asserted in malformed-input tests; fixture contract still passes.
    Evidence: .sisyphus/evidence/task-5-parser-suite.txt

  Scenario: Malformed embedded JSON fails predictably
    Tool: Bash
    Steps: Run `uv run pytest tests/test_next_data.py::test_malformed_next_data_raises_typed_parse_error -v | tee .sisyphus/evidence/task-5-malformed-json.txt`.
    Expected: Exit 0; failure mode is `CrawlerParseError` or a subclass, not bare `json.JSONDecodeError` or random `KeyError` confetti.
    Evidence: .sisyphus/evidence/task-5-malformed-json.txt
  ```

  **Commit**: YES | Message: `fix(crawler): normalize price parser states` | Files: [`src/ps_price_crawler/errors.py`, `src/ps_price_crawler/next_data.py`, `src/ps_price_crawler/catalog.py`, `src/ps_price_crawler/product.py`, `tests/test_next_data.py`, `tests/test_catalog.py`, `tests/test_product.py`, `tests/test_fixture_contract.py`]

- [x] 6. Snapshot source strategy decision and policy module

  **What to do**: Encode the milestone decision: **catalog-first, concept-detail fallback**. Create `src/ps_price_crawler/source_strategy.py` and `tests/test_source_strategy.py`. Policy: use catalog price for daily snapshot when normalized state is `FREE`, `PAID`, or `DISCOUNTED` and product IDs are present; fetch concept detail when catalog price is `UNKNOWN`, `PS_PLUS`, `UNAVAILABLE`, `NOT_PURCHASABLE`, product IDs are missing, or metadata needed for later Django fields (`publisher_name`, `release_date`, `top_category`) is absent. Document that full catalog detail backfill is out-of-scope; future sync should queue fallback detail fetches only for ambiguous/missing cases.
  **Must NOT do**: Do not implement scheduler, persistence, retry queue, or full 7,990-item detail crawl. The plan is choosing a steering wheel, not building a bus depot.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: architectural decision with downstream sync cost impact.
  - Skills: [`superpowers/test-driven-development`] - Policy should be tested as pure logic.
  - Omitted: [`superpowers/systematic-debugging`] - No failing runtime bug unless tests expose one.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 7, 8 | Blocked By: 2, 3

  **References**:
  - Spec sync flow: `docs/superpowers/specs/2026-04-27-ps-low-price-design.md:97-118` - daily catalog and price sync requirements.
  - Store product fields: `docs/superpowers/specs/2026-04-27-ps-low-price-design.md:44-84` - metadata needed later.
  - Spike known decision: `docs/spikes/ps-store-crawler-spike.md:33-38` - catalog vs detail question.
  - Catalog item model: `src/ps_price_crawler/models.py:18-25` - concept/product IDs and raw price.
  - Product detail model: `src/ps_price_crawler/models.py:38-48` - detail metadata fields.

  **Acceptance Criteria**:
  - [ ] `src/ps_price_crawler/source_strategy.py` exposes `SnapshotSourceDecision` and `choose_snapshot_source(catalog_item, normalized_price)`.
  - [ ] `tests/test_source_strategy.py` covers catalog-first decisions for `FREE`, `PAID`, `DISCOUNTED` with product IDs.
  - [ ] `tests/test_source_strategy.py` covers concept-detail fallback for `UNKNOWN`, `PS_PLUS`, `UNAVAILABLE`, `NOT_PURCHASABLE`, and missing product IDs.
  - [ ] `docs/spikes/ps-store-crawler-spike.md` records the catalog-first/detail-fallback decision and explicitly keeps full detail backfill out of this milestone.
  - [ ] `uv run pytest tests/test_source_strategy.py -v` exits `0`.

  **QA Scenarios**:
  ```
  Scenario: Pure source strategy logic is deterministic
    Tool: Bash
    Steps: Run `uv run pytest tests/test_source_strategy.py -v | tee .sisyphus/evidence/task-6-source-strategy.txt`.
    Expected: Exit 0; tests prove catalog-first for clear prices and concept fallback for ambiguous/missing states.
    Evidence: .sisyphus/evidence/task-6-source-strategy.txt

  Scenario: Spike doc records the decision and excludes full backfill
    Tool: Bash
    Steps: Run `python3 - <<'PY'\nfrom pathlib import Path\ndoc=Path('docs/spikes/ps-store-crawler-spike.md').read_text()\nassert 'catalog-first' in doc.lower() or 'catalog first' in doc.lower()\nassert 'concept-detail fallback' in doc.lower() or 'concept detail fallback' in doc.lower()\nassert 'full' in doc.lower() and 'backfill' in doc.lower()\nPY`
    Expected: Exit 0; doc contains source strategy and explicit non-goal.
    Evidence: .sisyphus/evidence/task-6-doc-source-strategy.txt
  ```

  **Commit**: YES | Message: `docs(crawler): choose snapshot source strategy` | Files: [`src/ps_price_crawler/source_strategy.py`, `tests/test_source_strategy.py`, `docs/spikes/ps-store-crawler-spike.md`]

- [x] 7. CLI JSON output and fixture report contract

  **What to do**: Turn the spike CLI into a reliable verification/reporting interface without adding persistence. Add `--format text|json` to `catalog` and `concept` commands. JSON output must include normalized price state, concept ID, product IDs, selected source strategy, and parser error objects for failed items. Add `fixture-report --fixtures tests/fixtures/ps_store --output .sisyphus/evidence/task-7-fixture-report.json` to summarize committed fixtures and states. Existing text output should remain backward-compatible enough that README examples still make sense.
  **Must NOT do**: Do not add database writes, scheduler flags, or background crawling. CLI is a microscope here, not a forklift.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: CLI behavior and parser integration have multiple edge cases.
  - Skills: [`superpowers/test-driven-development`] - CLI output contract must be test-first.
  - Omitted: [`frontend-ui-ux`] - No browser interactions.

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: 8 | Blocked By: 5, 6

  **References**:
  - CLI parser setup: `src/ps_price_crawler/cli.py:11-31` - add arguments/subcommand.
  - Catalog output: `src/ps_price_crawler/cli.py:34-49` - preserve text and add JSON.
  - Concept output: `src/ps_price_crawler/cli.py:51-62` - preserve text and add JSON.
  - Normalized contract: `src/ps_price_crawler/price_contract.py` from Task 2.
  - Source strategy: `src/ps_price_crawler/source_strategy.py` from Task 6.
  - Fixture contract: `tests/fixtures/ps_store/` and `tests/test_fixture_contract.py` from Task 4.

  **Acceptance Criteria**:
  - [ ] `uv run ps-price-crawler fixture-report --fixtures tests/fixtures/ps_store --output .sisyphus/evidence/task-7-fixture-report.json` exits `0` and writes a JSON report containing all required states.
  - [ ] `tests/test_cli_json.py` covers JSON output without live network by injecting or monkeypatching client responses.
  - [ ] `uv run pytest tests/test_cli_json.py -v` exits `0`.
  - [ ] `python3 - <<'PY'\nimport json\nfrom pathlib import Path\nreport=json.loads(Path('.sisyphus/evidence/task-7-fixture-report.json').read_text())\nassert 'fixtures' in report and isinstance(report['fixtures'], list) and report['fixtures']\nPY` exits `0`.

  **QA Scenarios**:
  ```
  Scenario: CLI JSON tests pass offline
    Tool: Bash
    Steps: Run `uv run pytest tests/test_cli_json.py -v | tee .sisyphus/evidence/task-7-cli-json-tests.txt`.
    Expected: Exit 0; tests validate JSON shape for catalog, concept, and fixture-report without network.
    Evidence: .sisyphus/evidence/task-7-cli-json-tests.txt

  Scenario: Fixture report contains every required state
    Tool: Bash
    Steps: Run `uv run ps-price-crawler fixture-report --fixtures tests/fixtures/ps_store --output .sisyphus/evidence/task-7-fixture-report.json && python3 - <<'PY'\nimport json\nfrom pathlib import Path\nreport=json.loads(Path('.sisyphus/evidence/task-7-fixture-report.json').read_text())\nstates={item['state'] for item in report['fixtures']}\nrequired={'FREE','PAID','DISCOUNTED','PS_PLUS'}\nassert required <= states, states\nassert any(s in states for s in {'UNAVAILABLE','NOT_PURCHASABLE','UNKNOWN'})\nPY`
    Expected: Exit 0; report includes free, paid, discounted, PS Plus, and unavailable/not-purchasable/unknown coverage.
    Evidence: .sisyphus/evidence/task-7-fixture-report.json

  Scenario: Live smoke JSON commands work outside CI
    Tool: Bash
    Steps: Run `uv run ps-price-crawler concept 223118 --format json > .sisyphus/evidence/task-7-live-concept.json && uv run ps-price-crawler catalog --pages 2 --format json > .sisyphus/evidence/task-7-live-catalog.json && python3 - <<'PY'\nimport json\nfrom pathlib import Path\nconcept=json.loads(Path('.sisyphus/evidence/task-7-live-concept.json').read_text())\ncatalog=json.loads(Path('.sisyphus/evidence/task-7-live-catalog.json').read_text())\nassert concept['concept_id'] == '223118'\nassert concept['price']['state'] == 'FREE'\nassert 'pages' in catalog and 'items' in catalog\nPY`.
    Expected: Exit 0 when network and PlayStation Store are reachable; failures due to network/HTTP status must be captured in `.sisyphus/evidence/task-7-live-smoke-failure.txt` and do not change offline CI acceptance.
    Evidence: .sisyphus/evidence/task-7-live-concept.json and .sisyphus/evidence/task-7-live-catalog.json
  ```

  **Commit**: YES | Message: `feat(crawler): report normalized fixture coverage` | Files: [`src/ps_price_crawler/cli.py`, `tests/test_cli_json.py`]

- [x] 8. Documentation update and Django data-foundation handoff

  **What to do**: Update `README.md` and `docs/spikes/ps-store-crawler-spike.md` so the repo no longer reads like an unfinished spike with known gaps hanging off it like loose wires. Document canonical `uv` setup, offline tests, live fixture refresh commands, source strategy, fixture coverage, CI policy, and the exact next milestone: Django data foundation only after crawler contract stabilization is verified. Add a “Next milestone input” section listing fields Django models can rely on and fields still treated as source-risk.
  **Must NOT do**: Do not create the Django plan here and do not edit files outside documentation/README unless a verification command in this task requires a tiny import-path fix. This task is the handoff, not the sequel.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: docs/handoff with technical precision.
  - Skills: [] - No extra skill required beyond plan instructions.
  - Omitted: [`superpowers/test-driven-development`] - Documentation task verified by commands and existing tests.

  **Parallelization**: Can Parallel: NO | Wave 5 | Blocks: Final Verification Wave | Blocked By: 1, 2, 3, 4, 5, 6, 7

  **References**:
  - README current milestone: `README.md:5-23` - update commands and milestone status.
  - Data source notes: `README.md:25-32` - keep non-public SSR risk warning.
  - Spike result and gaps: `docs/spikes/ps-store-crawler-spike.md:20-38` - replace unresolved gaps with fixture coverage and source strategy.
  - Future v1 spec: `docs/superpowers/specs/2026-04-27-ps-low-price-design.md:44-118` - handoff should align with StoreProduct/PriceSnapshot/SyncRun/SyncError needs.

  **Acceptance Criteria**:
  - [ ] README documents `uv sync --extra dev`, `uv run pytest -v`, `uv run ps-price-crawler catalog --pages 2 --format json`, and `uv run ps-price-crawler fixture-report --fixtures tests/fixtures/ps_store`.
  - [ ] `docs/spikes/ps-store-crawler-spike.md` has no unresolved bullet saying “Confirm a discounted paid product fixture”, “Confirm a PS Plus price fixture”, or “Decide whether catalog page price is sufficient”.
  - [ ] `docs/spikes/ps-store-crawler-spike.md` documents catalog-first/detail-fallback source strategy.
  - [ ] `uv run pytest -v` exits `0`.
  - [ ] `python3 - <<'PY'\nfrom pathlib import Path\nallowed_prefixes=('.github/workflows/','src/ps_price_crawler/','tests/','docs/spikes/','README.md','pyproject.toml','uv.lock','.gitignore')\nchanged=[line[3:] for line in Path('.sisyphus/evidence/task-8-git-status.txt').read_text().splitlines() if line.strip()]\nfor path in changed:\n    assert path.startswith(allowed_prefixes), path\nPY` exits `0` after `git status --short | tee .sisyphus/evidence/task-8-git-status.txt`.

  **QA Scenarios**:
  ```
  Scenario: Documentation no longer advertises resolved gaps as open
    Tool: Bash
    Steps: Run `python3 - <<'PY'\nfrom pathlib import Path\ndoc=Path('docs/spikes/ps-store-crawler-spike.md').read_text()\nfor phrase in ['Confirm a discounted paid product fixture','Confirm a PS Plus price fixture','Decide whether catalog page price is sufficient']:\n    assert phrase not in doc, phrase\nassert 'catalog' in doc.lower() and 'fallback' in doc.lower()\nPY`
    Expected: Exit 0; old unresolved gap wording is gone and source strategy is documented.
    Evidence: .sisyphus/evidence/task-8-doc-gap-check.txt

  Scenario: Full offline verification passes after handoff docs
    Tool: Bash
    Steps: Run `uv run pytest -v | tee .sisyphus/evidence/task-8-full-pytest.txt`.
    Expected: Exit 0; all offline tests pass after documentation and handoff changes.
    Evidence: .sisyphus/evidence/task-8-full-pytest.txt
  ```

  **Commit**: YES | Message: `docs: record crawler contract stabilization` | Files: [`README.md`, `docs/spikes/ps-store-crawler-spike.md`]

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Commit once per task when tests pass.
- Suggested commit messages are listed inside each task.
- Do not commit ignored live raw captures under `tests/fixtures/live/`.
- Do commit deterministic fixtures under `tests/fixtures/ps_store/`; raw HTML fixtures are allowed only when each HTML file is `<= 2 MiB` and the total fixture directory is `<= 10 MiB`, otherwise commit normalized JSON plus SHA-256/size metadata only.

## Success Criteria
- Repo has a stable crawler adapter contract ready for a later Django data foundation plan.
- Offline test suite passes through `uv run pytest -v`.
- CI exists and matches the offline verification policy.
- Spike doc no longer has unresolved fixture gaps; any remaining source fragility is documented as known external dependency risk, not as parser ambiguity.
