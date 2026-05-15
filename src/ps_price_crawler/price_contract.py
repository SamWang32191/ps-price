from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ps_price_crawler.models import PriceInfo


class PriceState(str, Enum):
    FREE = "FREE"
    PAID = "PAID"
    DISCOUNTED = "DISCOUNTED"
    PS_PLUS = "PS_PLUS"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_PURCHASABLE = "NOT_PURCHASABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class NormalizedPrice:
    state: PriceState
    currency: str | None
    base_amount_cents: int | None
    discounted_amount_cents: int | None
    plus_amount_cents: int | None
    base_display: str | None
    discounted_display: str | None
    discount_text: str | None
    service_branding: tuple[str, ...]
    upsell_text: str | None
    source: str
    raw_missing_reason: str | None


def normalize_price_info(
    raw_price: PriceInfo | None,
    source: str,
    *,
    raw_missing_reason: str | None = None,
) -> NormalizedPrice:
    if raw_price is None:
        return NormalizedPrice(
            state=PriceState.UNKNOWN,
            currency=None,
            base_amount_cents=None,
            discounted_amount_cents=None,
            plus_amount_cents=None,
            base_display=None,
            discounted_display=None,
            discount_text=None,
            service_branding=(),
            upsell_text=None,
            source=source,
            raw_missing_reason=raw_missing_reason,
        )

    base_display = _clean_display(raw_price.base_price)
    discounted_display = _clean_display(raw_price.discounted_price)
    currency = "TWD"

    discount_text = _clean_display(raw_price.discount_text)
    upsell_text = _clean_display(raw_price.upsell_text)
    service_branding = tuple(raw_price.service_branding)

    base_amount_cents = _parse_twd_cents(base_display)
    discounted_amount_cents = _parse_twd_cents(discounted_display)

    state = _normalize_state(
        raw_price,
        base_display=base_display,
        discounted_display=discounted_display,
        base_amount_cents=base_amount_cents,
        discounted_amount_cents=discounted_amount_cents,
        discount_text=discount_text,
    )

    if state == PriceState.PS_PLUS:
        plus_amount_cents = discounted_amount_cents
    else:
        plus_amount_cents = None

    return NormalizedPrice(
        state=state,
        currency=currency,
        base_amount_cents=base_amount_cents,
        discounted_amount_cents=discounted_amount_cents,
        plus_amount_cents=plus_amount_cents,
        base_display=base_display,
        discounted_display=discounted_display,
        discount_text=discount_text,
        service_branding=service_branding,
        upsell_text=upsell_text,
        source=source,
        raw_missing_reason=raw_missing_reason,
    )


def _normalize_state(
    raw_price: PriceInfo,
    *,
    base_display: str | None,
    discounted_display: str | None,
    base_amount_cents: int | None,
    discounted_amount_cents: int | None,
    discount_text: str | None,
) -> PriceState:
    if _is_unavailable_display(base_display) or _is_unavailable_display(discounted_display):
        return PriceState.UNAVAILABLE

    if _is_not_purchasable_display(base_display) or _is_not_purchasable_display(discounted_display):
        return PriceState.NOT_PURCHASABLE

    if _has_plus_signal(raw_price):
        return PriceState.PS_PLUS

    if _is_free(raw_price, base_display=base_display, discounted_display=discounted_display,
               base_amount_cents=base_amount_cents, discounted_amount_cents=discounted_amount_cents):
        return PriceState.FREE

    if _is_discounted(base_display=base_display, discounted_display=discounted_display,
                      base_amount_cents=base_amount_cents,
                      discounted_amount_cents=discounted_amount_cents,
                      discount_text=discount_text):
        return PriceState.DISCOUNTED

    if all(value is not None for value in (base_amount_cents, discounted_amount_cents)):
        return PriceState.PAID

    return PriceState.UNKNOWN


def _clean_display(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _parse_twd_cents(text: str | None) -> int | None:
    if text is None:
        return None

    if text == "免費":
        return 0

    normalized = text.replace("NT$", "").replace(",", "").strip()
    if not normalized:
        return None

    try:
        return int(normalized) * 100
    except ValueError:
        return None


def _is_free(
    raw_price: PriceInfo,
    *,
    base_display: str | None,
    discounted_display: str | None,
    base_amount_cents: int | None,
    discounted_amount_cents: int | None,
) -> bool:
    if raw_price.is_free:
        return True

    if (base_display == "免費" and discounted_display == "免費"):
        return True

    if base_amount_cents == 0 and discounted_amount_cents == 0:
        return True

    return False


def _is_discounted(
    *,
    base_display: str | None,
    discounted_display: str | None,
    base_amount_cents: int | None,
    discounted_amount_cents: int | None,
    discount_text: str | None,
) -> bool:
    if discount_text:
        return True

    if base_display == discounted_display:
        return False

    if base_amount_cents is not None and discounted_amount_cents is not None:
        return base_amount_cents != discounted_amount_cents

    return False


def _has_plus_signal(raw_price: PriceInfo) -> bool:
    if raw_price.is_exclusive or raw_price.is_tied_to_subscription:
        return True

    if _contains_plus_keyword(raw_price.upsell_text):
        return True

    for branding in raw_price.service_branding:
        if _contains_plus_keyword(branding):
            return True

    return False


def _contains_plus_keyword(value: str | None) -> bool:
    if not value:
        return False

    candidate = value.lower()
    return (
        "plus" in candidate
        or "ps+" in candidate
        or "ps plus" in candidate
        or "playstation plus" in candidate
    )


def _is_unavailable_display(text: str | None) -> bool:
    if not text:
        return False
    unavailable_tokens = {
        "暫無售價",
        "售價暫缺",
        "not available",
        "暫時無法購買",
    }
    return text.strip() in unavailable_tokens


def _is_not_purchasable_display(text: str | None) -> bool:
    if not text:
        return False
    not_purchasable_tokens = {
        "不可購買",
        "不提供購買",
        "無法購買",
        "not for purchase",
    }
    return text.strip() in not_purchasable_tokens
