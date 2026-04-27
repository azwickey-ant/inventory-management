"""
Tests for restocking API endpoints.
"""

import pytest


class TestRestockingRecommendations:
    """Test suite for GET /api/restocking/recommendations."""

    def test_get_recommendations_full_budget(self, client):
        """A budget exceeding the full restock cost returns unscaled quantities."""
        response = client.get("/api/restocking/recommendations?budget=1000000")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)
        assert data["budget"] == 1000000
        assert data["scaled"] is False
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0
        assert abs(data["total_cost"] - data["full_restock_cost"]) < 0.01

    def test_get_recommendations_only_low_stock_items(self, client):
        """Every recommended item is at or below its reorder point."""
        response = client.get("/api/restocking/recommendations?budget=100000")
        assert response.status_code == 200

        data = response.json()
        for item in data["items"]:
            assert item["quantity_on_hand"] <= item["reorder_point"]
            assert item["recommended_quantity"] >= 1

    def test_recommendation_item_structure(self, client):
        """Recommended items expose all fields the UI needs."""
        response = client.get("/api/restocking/recommendations?budget=100000")
        data = response.json()

        required_fields = {
            "sku",
            "name",
            "category",
            "warehouse",
            "quantity_on_hand",
            "reorder_point",
            "unit_cost",
            "recommended_quantity",
            "line_cost",
        }
        for item in data["items"]:
            assert required_fields <= item.keys()
            assert isinstance(item["recommended_quantity"], int)
            assert isinstance(item["unit_cost"], (int, float))
            assert isinstance(item["line_cost"], (int, float))

    def test_recommendation_line_cost_calculation(self, client):
        """line_cost == recommended_quantity * unit_cost."""
        response = client.get("/api/restocking/recommendations?budget=100000")
        data = response.json()

        for item in data["items"]:
            expected = item["recommended_quantity"] * item["unit_cost"]
            assert abs(item["line_cost"] - expected) < 0.01

    def test_get_recommendations_scaled_budget(self, client):
        """A budget below full cost scales quantities so total stays within budget."""
        response = client.get("/api/restocking/recommendations?budget=10000")
        assert response.status_code == 200

        data = response.json()
        assert data["scaled"] is True
        assert data["total_cost"] <= 10000
        assert data["total_cost"] < data["full_restock_cost"]
        for item in data["items"]:
            assert item["recommended_quantity"] >= 1

    def test_get_recommendations_zero_budget_rejected(self, client):
        """Budget of zero is rejected with 400."""
        response = client.get("/api/restocking/recommendations?budget=0")
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data
        assert "greater than 0" in data["detail"].lower()

    def test_get_recommendations_negative_budget_rejected(self, client):
        """Negative budget is rejected with 400."""
        response = client.get("/api/restocking/recommendations?budget=-500")
        assert response.status_code == 400


class TestRestockingOrders:
    """Test suite for POST /api/restocking/orders."""

    def test_create_restock_order(self, client):
        """Creating a restock order returns a well-formed Order."""
        response = client.post("/api/restocking/orders", json={"budget": 50000})
        assert response.status_code == 200

        order = response.json()
        assert order["order_type"] == "restock"
        assert order["status"] == "Submitted"
        assert order["customer"] == "Internal Restock"
        assert order["order_number"].startswith("RST-")
        assert isinstance(order["lead_time_days"], int)
        assert order["lead_time_days"] > 0
        assert order["total_value"] > 0
        assert len(order["items"]) > 0

        for item in order["items"]:
            assert "sku" in item
            assert "name" in item
            assert isinstance(item["quantity"], int)
            assert isinstance(item["unit_price"], (int, float))

    def test_created_order_appears_in_orders_list(self, client):
        """A submitted restock order is returned by GET /api/orders."""
        create_response = client.post("/api/restocking/orders", json={"budget": 30000})
        assert create_response.status_code == 200
        created = create_response.json()

        list_response = client.get("/api/orders")
        assert list_response.status_code == 200
        all_orders = list_response.json()

        match = next((o for o in all_orders if o["id"] == created["id"]), None)
        assert match is not None
        assert match["order_type"] == "restock"
        assert match["lead_time_days"] == created["lead_time_days"]

    def test_create_restock_order_zero_budget_rejected(self, client):
        """Zero budget is rejected with 400."""
        response = client.post("/api/restocking/orders", json={"budget": 0})
        assert response.status_code == 400

    def test_expected_delivery_matches_lead_time(self, client):
        """expected_delivery is order_date + lead_time_days."""
        from datetime import datetime

        response = client.post("/api/restocking/orders", json={"budget": 40000})
        order = response.json()

        order_date = datetime.fromisoformat(order["order_date"])
        expected_delivery = datetime.fromisoformat(order["expected_delivery"])
        delta_days = (expected_delivery - order_date).days
        assert delta_days == order["lead_time_days"]


class TestOrdersRegression:
    """Ensure the Order model extension doesn't break existing customer orders."""

    def test_existing_orders_still_validate(self, client):
        """GET /api/orders still returns 200 with order_type defaulting for legacy rows."""
        response = client.get("/api/orders")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0

        customer_orders = [o for o in data if o["order_type"] == "customer"]
        assert len(customer_orders) > 0
        for order in customer_orders:
            assert order["lead_time_days"] is None
