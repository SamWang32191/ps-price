from __future__ import annotations

import pytest
from django.db import IntegrityError

from ps_price_sync.models import StoreProduct
from ps_price_web.models import WatchedProduct


def _product(product_id: str = "P-WATCHED", name: str = "Watched Product") -> StoreProduct:
    return StoreProduct.objects.create(product_id=product_id, product_name=name, is_visible=True, missing_count=0)


@pytest.mark.django_db
def test_watched_product_belongs_to_one_product() -> None:
    product = _product()

    watched = WatchedProduct.objects.create(store_product=product, target_price_cents=59000)

    assert watched.store_product == product
    assert product.watch == watched
    assert watched.target_price_cents == 59000


@pytest.mark.django_db
def test_watched_product_is_one_to_one_per_product() -> None:
    product = _product()
    WatchedProduct.objects.create(store_product=product, target_price_cents=59000)

    with pytest.raises(IntegrityError):
        WatchedProduct.objects.create(store_product=product, target_price_cents=49000)


@pytest.mark.django_db
def test_watched_product_allows_empty_target_price() -> None:
    product = _product()

    watched = WatchedProduct.objects.create(store_product=product, target_price_cents=None)

    assert watched.target_price_cents is None


@pytest.mark.django_db
def test_watched_product_is_deleted_when_product_is_deleted() -> None:
    product = _product()
    watched = WatchedProduct.objects.create(store_product=product, target_price_cents=59000)

    product.delete()

    assert not WatchedProduct.objects.filter(id=watched.id).exists()
