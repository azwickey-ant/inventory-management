from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from uuid import uuid4
from datetime import datetime, timedelta
from math import floor
from mock_data import (
    inventory_items,
    orders,
    demand_forecasts,
    backlog_items,
    spending_summary,
    monthly_spending,
    category_spending,
    recent_transactions,
    purchase_orders,
)

app = FastAPI(title="Factory Inventory Management System")

# Supplier lead times by inventory category. A restock order's lead time is the
# max across its line items so the whole order arrives together.
LEAD_TIME_DAYS = {
    "Circuit Boards": 12,
    "Sensors": 7,
    "Actuators": 14,
    "Controllers": 10,
    "Power Supplies": 9,
}
DEFAULT_LEAD_TIME_DAYS = 14

# Quarter mapping for date filtering
QUARTER_MAP = {
    "Q1-2025": ["2025-01", "2025-02", "2025-03"],
    "Q2-2025": ["2025-04", "2025-05", "2025-06"],
    "Q3-2025": ["2025-07", "2025-08", "2025-09"],
    "Q4-2025": ["2025-10", "2025-11", "2025-12"],
}


def filter_by_month(items: list, month: Optional[str]) -> list:
    """Filter items by month/quarter based on order_date field"""
    if not month or month == "all":
        return items

    if month.startswith("Q"):
        # Handle quarters
        if month in QUARTER_MAP:
            months = QUARTER_MAP[month]
            return [
                item
                for item in items
                if any(m in item.get("order_date", "") for m in months)
            ]
    else:
        # Direct month match
        return [item for item in items if month in item.get("order_date", "")]

    return items


def apply_filters(
    items: list,
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
) -> list:
    """Apply common filters to a list of items"""
    filtered = items

    if warehouse and warehouse != "all":
        filtered = [item for item in filtered if item.get("warehouse") == warehouse]

    if category and category != "all":
        filtered = [
            item
            for item in filtered
            if item.get("category", "").lower() == category.lower()
        ]

    if status and status != "all":
        filtered = [
            item
            for item in filtered
            if item.get("status", "").lower() == status.lower()
        ]

    return filtered


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Data models
class InventoryItem(BaseModel):
    id: str
    sku: str
    name: str
    category: str
    warehouse: str
    quantity_on_hand: int
    reorder_point: int
    unit_cost: float
    location: str
    last_updated: str


class Order(BaseModel):
    id: str
    order_number: str
    customer: str
    items: List[dict]
    status: str
    order_date: str
    expected_delivery: str
    total_value: float
    actual_delivery: Optional[str] = None
    warehouse: Optional[str] = None
    category: Optional[str] = None
    order_type: Optional[str] = "customer"
    lead_time_days: Optional[int] = None


class DemandForecast(BaseModel):
    id: str
    item_sku: str
    item_name: str
    current_demand: int
    forecasted_demand: int
    trend: str
    period: str


class BacklogItem(BaseModel):
    id: str
    order_id: str
    item_sku: str
    item_name: str
    quantity_needed: int
    quantity_available: int
    days_delayed: int
    priority: str
    has_purchase_order: Optional[bool] = False


class PurchaseOrder(BaseModel):
    id: str
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    status: str
    created_date: str
    notes: Optional[str] = None


class CreatePurchaseOrderRequest(BaseModel):
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    notes: Optional[str] = None


class RestockLineItem(BaseModel):
    sku: str
    name: str
    category: str
    warehouse: str
    quantity_on_hand: int
    reorder_point: int
    unit_cost: float
    recommended_quantity: int
    line_cost: float


class RestockRecommendations(BaseModel):
    budget: float
    items: List[RestockLineItem]
    total_cost: float
    full_restock_cost: float
    scaled: bool


class CreateRestockOrderRequest(BaseModel):
    budget: float


def _compute_restock_recommendations(budget: float) -> dict:
    """Build a restock plan that fits within `budget`.

    Eligible items are those at or below their reorder point. Each is restocked
    toward 2x its reorder point. If the full plan exceeds the budget, every
    quantity is scaled down by the same ratio (floor, min 1) so all eligible
    items still receive some allocation rather than dropping the cheapest.
    """
    eligible = [
        i for i in inventory_items if i["quantity_on_hand"] <= i["reorder_point"]
    ]

    full_items = []
    for i in eligible:
        target_qty = i["reorder_point"] * 2 - i["quantity_on_hand"]
        full_items.append(
            {
                "sku": i["sku"],
                "name": i["name"],
                "category": i["category"],
                "warehouse": i["warehouse"],
                "quantity_on_hand": i["quantity_on_hand"],
                "reorder_point": i["reorder_point"],
                "unit_cost": i["unit_cost"],
                "recommended_quantity": target_qty,
                "line_cost": round(target_qty * i["unit_cost"], 2),
            }
        )

    full_cost = round(sum(item["line_cost"] for item in full_items), 2)
    scaled = full_cost > budget and full_cost > 0

    if scaled:
        ratio = budget / full_cost
        for item in full_items:
            qty = max(1, floor(item["recommended_quantity"] * ratio))
            item["recommended_quantity"] = qty
            item["line_cost"] = round(qty * item["unit_cost"], 2)

    total_cost = round(sum(item["line_cost"] for item in full_items), 2)

    return {
        "budget": budget,
        "items": full_items,
        "total_cost": total_cost,
        "full_restock_cost": full_cost,
        "scaled": scaled,
    }


# API endpoints
@app.get("/")
def root():
    return {"message": "Factory Inventory Management System API", "version": "1.0.0"}


@app.get("/api/inventory", response_model=List[InventoryItem])
def get_inventory(warehouse: Optional[str] = None, category: Optional[str] = None):
    """Get all inventory items with optional filtering"""
    return apply_filters(inventory_items, warehouse, category)


@app.get("/api/inventory/{item_id}", response_model=InventoryItem)
def get_inventory_item(item_id: str):
    """Get a specific inventory item"""
    item = next((item for item in inventory_items if item["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.get("/api/orders", response_model=List[Order])
def get_orders(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None,
):
    """Get all orders with optional filtering"""
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)
    return filtered_orders


@app.get("/api/orders/{order_id}", response_model=Order)
def get_order(order_id: str):
    """Get a specific order"""
    order = next((order for order in orders if order["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.get("/api/demand", response_model=List[DemandForecast])
def get_demand_forecasts():
    """Get demand forecasts"""
    return demand_forecasts


@app.get("/api/backlog", response_model=List[BacklogItem])
def get_backlog():
    """Get backlog items with purchase order status"""
    # Add has_purchase_order flag to each backlog item
    result = []
    for item in backlog_items:
        item_dict = dict(item)
        # Check if this backlog item has a purchase order
        has_po = any(po["backlog_item_id"] == item["id"] for po in purchase_orders)
        item_dict["has_purchase_order"] = has_po
        result.append(item_dict)
    return result


@app.get("/api/dashboard/summary")
def get_dashboard_summary(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None,
):
    """Get summary statistics for dashboard with optional filtering"""
    # Filter inventory
    filtered_inventory = apply_filters(inventory_items, warehouse, category)

    # Filter orders
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)

    total_inventory_value = sum(
        item["quantity_on_hand"] * item["unit_cost"] for item in filtered_inventory
    )
    low_stock_items = len(
        [
            item
            for item in filtered_inventory
            if item["quantity_on_hand"] <= item["reorder_point"]
        ]
    )
    pending_orders = len(
        [
            order
            for order in filtered_orders
            if order["status"] in ["Processing", "Backordered"]
        ]
    )
    total_backlog_items = len(backlog_items)

    return {
        "total_inventory_value": round(total_inventory_value, 2),
        "low_stock_items": low_stock_items,
        "pending_orders": pending_orders,
        "total_backlog_items": total_backlog_items,
        "total_orders_value": sum(order["total_value"] for order in filtered_orders),
    }


@app.get("/api/spending/summary")
def get_spending_summary():
    """Get spending summary statistics"""
    return spending_summary


@app.get("/api/spending/monthly")
def get_monthly_spending():
    """Get monthly spending breakdown"""
    return monthly_spending


@app.get("/api/spending/categories")
def get_category_spending():
    """Get spending by category"""
    return category_spending


@app.get("/api/spending/transactions")
def get_recent_transactions():
    """Get recent transactions"""
    return recent_transactions


@app.get("/api/reports/quarterly")
def get_quarterly_reports():
    """Get quarterly performance reports"""
    # Calculate quarterly statistics from orders
    quarters = {}

    for order in orders:
        order_date = order.get("order_date", "")
        # Determine quarter
        if (
            "2025-01" in order_date
            or "2025-02" in order_date
            or "2025-03" in order_date
        ):
            quarter = "Q1-2025"
        elif (
            "2025-04" in order_date
            or "2025-05" in order_date
            or "2025-06" in order_date
        ):
            quarter = "Q2-2025"
        elif (
            "2025-07" in order_date
            or "2025-08" in order_date
            or "2025-09" in order_date
        ):
            quarter = "Q3-2025"
        elif (
            "2025-10" in order_date
            or "2025-11" in order_date
            or "2025-12" in order_date
        ):
            quarter = "Q4-2025"
        else:
            continue

        if quarter not in quarters:
            quarters[quarter] = {
                "quarter": quarter,
                "total_orders": 0,
                "total_revenue": 0,
                "delivered_orders": 0,
                "avg_order_value": 0,
            }

        quarters[quarter]["total_orders"] += 1
        quarters[quarter]["total_revenue"] += order.get("total_value", 0)
        if order.get("status") == "Delivered":
            quarters[quarter]["delivered_orders"] += 1

    # Calculate averages and fulfillment rate
    result = []
    for q, data in quarters.items():
        if data["total_orders"] > 0:
            data["avg_order_value"] = round(
                data["total_revenue"] / data["total_orders"], 2
            )
            data["fulfillment_rate"] = round(
                (data["delivered_orders"] / data["total_orders"]) * 100, 1
            )
        result.append(data)

    # Sort by quarter
    result.sort(key=lambda x: x["quarter"])
    return result


@app.get("/api/reports/monthly-trends")
def get_monthly_trends():
    """Get month-over-month trends"""
    months = {}

    for order in orders:
        order_date = order.get("order_date", "")
        if not order_date:
            continue

        # Extract month (format: YYYY-MM-DD)
        month = order_date[:7]  # Gets YYYY-MM

        if month not in months:
            months[month] = {
                "month": month,
                "order_count": 0,
                "revenue": 0,
                "delivered_count": 0,
            }

        months[month]["order_count"] += 1
        months[month]["revenue"] += order.get("total_value", 0)
        if order.get("status") == "Delivered":
            months[month]["delivered_count"] += 1

    # Convert to list and sort
    result = list(months.values())
    result.sort(key=lambda x: x["month"])
    return result


@app.get("/api/restocking/recommendations", response_model=RestockRecommendations)
def get_restock_recommendations(budget: float):
    """Recommend low-stock items to restock, scaled to fit the given budget."""
    if budget <= 0:
        raise HTTPException(status_code=400, detail="Budget must be greater than 0")
    return _compute_restock_recommendations(budget)


@app.post("/api/restocking/orders", response_model=Order)
def create_restock_order(request: CreateRestockOrderRequest):
    """Create an internal restock order from the current recommendation for the given budget."""
    if request.budget <= 0:
        raise HTTPException(status_code=400, detail="Budget must be greater than 0")

    plan = _compute_restock_recommendations(request.budget)
    if not plan["items"]:
        raise HTTPException(
            status_code=400, detail="No items currently need restocking"
        )

    lead_time = max(
        LEAD_TIME_DAYS.get(item["category"], DEFAULT_LEAD_TIME_DAYS)
        for item in plan["items"]
    )

    now = datetime.now()
    order = {
        "id": str(uuid4()),
        "order_number": f"RST-2025-{len(orders) + 1:04d}",
        "customer": "Internal Restock",
        "items": [
            {
                "sku": item["sku"],
                "name": item["name"],
                "quantity": item["recommended_quantity"],
                "unit_price": item["unit_cost"],
            }
            for item in plan["items"]
        ],
        "status": "Submitted",
        "order_type": "restock",
        "order_date": now.isoformat(timespec="seconds"),
        "lead_time_days": lead_time,
        "expected_delivery": (now + timedelta(days=lead_time)).isoformat(
            timespec="seconds"
        ),
        "total_value": plan["total_cost"],
        "actual_delivery": None,
        "warehouse": None,
        "category": None,
    }
    orders.append(order)
    return order


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
