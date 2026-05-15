# Problems: ps-price-crawler-stabilization

## 2026-05-15 Session Start
- Avoid duplicate live search: once Task 3 handles fixture discovery, Atlas should not manually rerun equivalent searches unless verifying task outputs.

## 2026-05-15 Task 4
- Downstream Task 5 should account for concept detail pages that contain purchasable CTA metadata but no `Product.price`; catalog-first/detail-fallback policy will need to avoid treating detail price absence as source truth for paid/discounted/PS Plus states.
