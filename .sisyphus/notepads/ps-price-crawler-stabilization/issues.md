# Issues: ps-price-crawler-stabilization

## 2026-05-15 Session Start
- No active blocker yet.
- Known future blocker condition: Task 3 live discovery exits `2` if required fixture target categories are incomplete; Task 4 must not proceed in that case.

## 2026-05-15 Context Gathering
- No implementation blocker found.
- System completion reminder incorrectly treated exploratory background agents as if top-level plan checkboxes should be completed; do not mark implementation tasks complete until actual Task 1/2 verification passes.

## 2026-05-15 Task 1
- No Task 1 blocker found. Existing untracked Task 2 files (`src/ps_price_crawler/price_contract.py`, `tests/test_price_contract.py`) were left untouched.

## 2026-05-15 Task 2 verification notes
- `lsp_diagnostics` is configured for `basedpyright` but unavailable in environment (`basedpyright-langserver` command missing), so diagnostics step could not execute yet.
- Initial full test run exposed only one false expectation (`暫無售價` mapped to `UNAVAILABLE` not `UNKNOWN`), resolved by aligning test assertions with explicit state mapping.

## 2026-05-15 Task 3 blocker
- Live fixture discovery is BLOCKED because pages 1-80 did not produce a `ps_plus_candidate`; command output keeps `ps_plus_candidate: null` and reports incomplete discovery.
- Blocker evidence recorded in `.sisyphus/evidence/task-3-fixture-targets-blocked.txt`; Task 4 must not proceed until PS Plus target discovery is resolved.
- `lsp_diagnostics` remains unavailable because `basedpyright-langserver` is not installed in this environment; pytest/build verification was used, but LSP could not provide code diagnostics.

## 2026-05-15 Task 3 blocker resolution
- PS Plus blocker resolved: source data was present in all-games catalog pages, but parser dropped `upsellServiceBranding`; no non-all-games category source was needed.
- `.sisyphus/evidence/task-3-fixture-targets-blocked.txt` was updated to historical RESOLVED evidence after live discovery exited 0 with all five keys non-null.
- `lsp_diagnostics` is still blocked by missing `basedpyright-langserver`; this is an environment/tooling issue, not a current Task 3 code failure.

## 2026-05-15 Task 4
- `lsp_diagnostics` for `tests/test_fixture_contract.py` could not run because `basedpyright-langserver` is not installed; pytest and size/status evidence were used as executable verification instead.
- Current concept detail payloads for paid `10002075`, discounted `231761`, and PS Plus `10014149` lack `Product.price`; fixtures document `ValueError: Missing required Product.price` for Task 5 hardening rather than faking values.
- Missing/unavailable target `10014992` has `Concept.defaultProduct` as `None`; fixture documents `ValueError: Missing required Concept.defaultProduct`.

## 2026-05-15 Task 5
- `lsp_diagnostics` remains blocked for all modified Python files because `basedpyright-langserver` is not installed in this environment; Task 5 verification used the required `uv run pytest ...` evidence files instead.

## 2026-05-15 Task 7
- `lsp_diagnostics` was attempted for `src/ps_price_crawler/cli.py` and `tests/test_cli_json.py`, but the environment still lacks `basedpyright-langserver`; verification used `uv run pytest tests/test_cli_json.py -v`, fixture-report JSON assertions, CLI help smoke, and full `uv run pytest -v` instead.
