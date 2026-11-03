"""
Tests for restocking order endpoints.
"""
import pytest

import main


@pytest.fixture(autouse=True)
def clear_restocking_orders():
    """Reset the in-memory restocking orders between tests."""
    main.restocking_orders.clear()
    yield
    main.restocking_orders.clear()


class TestDemandForecastRestockingFields:
    """Test suite for the cost and lead time fields restocking relies on."""

    def test_forecasts_have_cost_and_lead_time(self, client):
        """Test that every forecast has a positive unit cost and lead time."""
        response = client.get("/api/demand")
        data = response.json()

        for forecast in data:
            assert forecast["unit_cost"] > 0
            assert forecast["lead_time_days"] > 0


class TestRestockingOrderEndpoints:
    """Test suite for creating and listing restocking orders."""

    def test_no_restocking_orders_initially(self, client):
        """Test that the list is empty before any order is placed."""
        response = client.get("/api/restocking-orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_restocking_order(self, client):
        """Test placing an order prices items from the forecast."""
        response = client.post("/api/restocking-orders", json={
            "items": [{"sku": "WDG-001", "quantity": 10}],
            "budget": 1000
        })
        assert response.status_code == 201

        order = response.json()
        assert order["status"] == "Submitted"
        assert order["order_number"].startswith("RST-")
        assert order["items"][0]["name"] == "Industrial Widget Type A"
        assert order["items"][0]["unit_cost"] == 12.5
        assert order["total_cost"] == 125.0
        assert order["budget"] == 1000

    def test_lead_time_is_slowest_item(self, client):
        """Test that the order lead time is the longest item lead time."""
        response = client.post("/api/restocking-orders", json={
            "items": [
                {"sku": "GSK-203", "quantity": 1},
                {"sku": "MTR-304", "quantity": 1}
            ]
        })
        order = response.json()

        assert order["lead_time_days"] == 21
        assert order["expected_delivery"] > order["order_date"]

    def test_submitted_order_is_listed_newest_first(self, client):
        """Test that placed orders appear in the list, newest first."""
        first = client.post("/api/restocking-orders", json={"items": [{"sku": "WDG-001", "quantity": 1}]}).json()
        second = client.post("/api/restocking-orders", json={"items": [{"sku": "FLT-405", "quantity": 1}]}).json()

        data = client.get("/api/restocking-orders").json()
        assert [order["id"] for order in data] == [second["id"], first["id"]]

    def test_order_over_budget_is_rejected(self, client):
        """Test that an order costing more than the budget returns 400."""
        response = client.post("/api/restocking-orders", json={
            "items": [{"sku": "MTR-304", "quantity": 10}],
            "budget": 100
        })
        assert response.status_code == 400
        assert client.get("/api/restocking-orders").json() == []

    def test_unknown_sku_is_rejected(self, client):
        """Test that a SKU missing from the forecast returns 400."""
        response = client.post("/api/restocking-orders", json={"items": [{"sku": "NOPE-999", "quantity": 1}]})
        assert response.status_code == 400

    def test_empty_order_is_rejected(self, client):
        """Test that an order with no items returns 400."""
        response = client.post("/api/restocking-orders", json={"items": []})
        assert response.status_code == 400

    def test_duplicate_sku_is_rejected(self, client):
        """Test that the same SKU twice in one order returns 400."""
        response = client.post("/api/restocking-orders", json={
            "items": [{"sku": "WDG-001", "quantity": 1}, {"sku": "WDG-001", "quantity": 2}]
        })
        assert response.status_code == 400

    def test_non_positive_quantity_is_rejected(self, client):
        """Test that a zero quantity fails validation."""
        response = client.post("/api/restocking-orders", json={"items": [{"sku": "WDG-001", "quantity": 0}]})
        assert response.status_code == 422
