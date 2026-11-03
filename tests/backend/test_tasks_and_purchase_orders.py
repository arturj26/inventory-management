"""
Tests for task and purchase order API endpoints.
"""
import pytest

import main


@pytest.fixture(autouse=True)
def reset_state():
    """Tasks and purchase orders live in shared in-memory lists; restore them around each test."""
    original_pos = list(main.purchase_orders)
    main.tasks.clear()
    main.task_counter = 0
    yield
    main.tasks.clear()
    main.task_counter = 0
    # Mutate in place: mock_data and main share the same list object
    main.purchase_orders[:] = original_pos


def make_po(backlog_item_id="1", **overrides):
    payload = {
        "backlog_item_id": backlog_item_id,
        "supplier_name": "Acme Supply",
        "quantity": 350,
        "unit_cost": 8.2,
        "expected_delivery_date": "2025-12-01",
        "notes": "Rush",
    }
    payload.update(overrides)
    return payload


class TestTasksEndpoints:
    """Test suite for task endpoints."""

    def test_get_tasks_initially_empty(self, client):
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_task(self, client):
        response = client.post(
            "/api/tasks", json={"title": "Check stock", "priority": "high", "dueDate": "2025-10-08"}
        )
        assert response.status_code == 201
        task = response.json()
        assert task == {
            "id": "task-1", "title": "Check stock", "priority": "high",
            "dueDate": "2025-10-08", "status": "pending",
        }
        assert client.get("/api/tasks").json() == [task]

    def test_create_task_invalid_input(self, client):
        assert client.post("/api/tasks", json={"title": "", "dueDate": "2025-10-08"}).status_code == 422
        assert client.post("/api/tasks", json={"title": "x", "priority": "urgent", "dueDate": "2025-10-08"}).status_code == 422
        assert client.post("/api/tasks", json={"title": "x", "dueDate": "next week"}).status_code == 400

    def test_toggle_task(self, client):
        task_id = client.post("/api/tasks", json={"title": "x", "dueDate": "2025-10-08"}).json()["id"]
        assert client.patch(f"/api/tasks/{task_id}").json()["status"] == "completed"
        assert client.patch(f"/api/tasks/{task_id}").json()["status"] == "pending"

    def test_delete_task(self, client):
        task_id = client.post("/api/tasks", json={"title": "x", "dueDate": "2025-10-08"}).json()["id"]
        assert client.delete(f"/api/tasks/{task_id}").status_code == 200
        assert client.get("/api/tasks").json() == []

    def test_task_ids_not_reused_after_delete(self, client):
        first = client.post("/api/tasks", json={"title": "a", "dueDate": "2025-10-08"}).json()["id"]
        client.delete(f"/api/tasks/{first}")
        second = client.post("/api/tasks", json={"title": "b", "dueDate": "2025-10-08"}).json()["id"]
        assert first != second

    def test_nonexistent_task(self, client):
        for response in (client.patch("/api/tasks/task-999"), client.delete("/api/tasks/task-999")):
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()


class TestPurchaseOrderEndpoints:
    """Test suite for purchase order endpoints."""

    def test_create_purchase_order(self, client):
        response = client.post("/api/purchase-orders", json=make_po())
        assert response.status_code == 201
        po = response.json()
        assert po["backlog_item_id"] == "1"
        assert po["supplier_name"] == "Acme Supply"
        assert po["quantity"] == 350
        assert po["status"] == "Pending"
        assert po["id"].startswith("PO-")
        assert len(po["created_date"]) == 10  # YYYY-MM-DD

    def test_get_purchase_order_by_backlog_item(self, client):
        created = client.post("/api/purchase-orders", json=make_po()).json()
        response = client.get("/api/purchase-orders/1")
        assert response.status_code == 200
        assert response.json() == created

    def test_backlog_reports_purchase_order(self, client):
        client.post("/api/purchase-orders", json=make_po("2"))
        backlog = {b["id"]: b for b in client.get("/api/backlog").json()}
        assert backlog["2"]["has_purchase_order"] is True
        assert backlog["1"]["has_purchase_order"] is False

    def test_duplicate_purchase_order_rejected(self, client):
        client.post("/api/purchase-orders", json=make_po())
        response = client.post("/api/purchase-orders", json=make_po())
        assert response.status_code == 400
        assert "already has" in response.json()["detail"]

    def test_unknown_backlog_item(self, client):
        response = client.post("/api/purchase-orders", json=make_po("999"))
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_nonexistent_purchase_order(self, client):
        response = client.get("/api/purchase-orders/1")
        assert response.status_code == 404

    def test_invalid_purchase_order_input(self, client):
        assert client.post("/api/purchase-orders", json=make_po(quantity=0)).status_code == 422
        assert client.post("/api/purchase-orders", json=make_po(unit_cost=-1)).status_code == 422
        assert client.post("/api/purchase-orders", json=make_po(supplier_name="")).status_code == 422
        assert client.post("/api/purchase-orders", json=make_po(expected_delivery_date="soon")).status_code == 400
