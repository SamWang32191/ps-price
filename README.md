# ps-price

Self-hosted PlayStation Store Taiwan price tracker.

## Current milestone

The first milestone is a crawler spike. It validates that Taiwan PlayStation Store SSR pages expose enough embedded JSON to parse:

- catalog page totals and concept IDs
- concept/product names
- platform and product category fields
- visible public price fields

## Spike commands

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
ps-price-crawler catalog --pages 2 --save-fixtures tests/fixtures/live
ps-price-crawler concept 223118 --save-fixtures tests/fixtures/live
```

## Data source notes

The crawler spike starts from PlayStation Store Taiwan SSR pages:

- catalog: `/zh-hant-tw/category/28c9c2b2-cecc-415c-9a08-482a605cb104/{page}`
- concept detail: `/zh-hant-tw/concept/{conceptId}`

The parser reads embedded `__NEXT_DATA__` and `env:*` JSON script payloads. This is a non-public implementation detail of the PlayStation Store website, so parser failures are treated as expected maintenance events.
