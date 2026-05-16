from __future__ import annotations

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_dashboard_route_renders_empty_state(client) -> None:
    response = client.get(reverse("dashboard"))

    assert response.status_code == 200
    assert "PS Price" in response.content.decode()
    assert "尚無同步紀錄" in response.content.decode()


@pytest.mark.django_db
def test_product_list_route_renders_empty_state(client) -> None:
    response = client.get(reverse("product-list"))

    assert response.status_code == 200
    assert "商品查詢" in response.content.decode()
    assert "目前沒有符合條件的商品" in response.content.decode()


@pytest.mark.django_db
def test_product_detail_returns_404_for_unknown_product(client) -> None:
    response = client.get(reverse("product-detail", kwargs={"product_id": "missing-product"}))

    assert response.status_code == 404
