# Decisions: ps-price-crawler-stabilization

## 2026-05-15 Session Start
- Use `uv` as canonical verification path because `python` command is absent and `python3` lacks pytest in the current environment.
- Execute plan through Atlas delegation; Atlas verifies and updates plan checkboxes only after evidence passes.
- Respect plan dependency matrix: Wave 1 tasks 1 and 2 can begin immediately; Task 3 depends on Task 1.

## 2026-05-15 Context Gathering
- Do not mark plan checkboxes for exploratory background agents; they were not top-level implementation tasks.
- Task 1 CI should include `--locked` in sync if feasible, even though plan acceptance only requires `uv sync --extra dev`; this prevents accidental lockfile drift in CI.
- Task 2 should preserve raw `PriceInfo` semantics and add a separate normalized contract module.

## 2026-05-15 Task 4
- Kept raw HTML committed in `tests/fixtures/ps_store/` because all individual files and total fixture directory size are below the plan limits; no docs update was needed, leaving `docs/spikes/ps-store-crawler-spike.md` for Task 6/8.
- Treated catalog fixture target state as the fixture-level `normalized_state`; concept detail parsing is recorded separately because detail pages can omit price fields even when catalog has price evidence.
- Did not modify parser code in Task 4; parser gaps are documented through fixture JSON `parser_error` values for downstream Task 5.
