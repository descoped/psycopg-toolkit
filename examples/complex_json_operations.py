#!/usr/bin/env python3
"""
Advanced JSONB Operations Example for psycopg-toolkit

This example demonstrates complex JSONB operations including:
- Complex nested JSON structures
- Bulk operations with JSONB data
- Transaction handling with JSONB
- Direct JSONB queries using PostgreSQL operators
- Performance optimization techniques
- Error handling and edge cases
"""

import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from psycopg_toolkit import (
    BaseRepository,
    Database,
    DatabaseSettings,
    RecordNotFoundError,
    TransactionManager,
)


# Complex models with nested JSONB structures
class OrderItem(BaseModel):
    """Individual item in an order."""

    product_id: UUID
    name: str
    quantity: int
    unit_price: Decimal
    discounts: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None


class ShippingAddress(BaseModel):
    """Shipping address details."""

    street: str
    city: str
    state: str
    postal_code: str
    country: str
    instructions: str | None = None
    coordinates: dict[str, float] | None = None  # {"lat": 0.0, "lon": 0.0}


class Order(BaseModel):
    """Complex order model with multiple JSONB fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    order_number: str
    customer_id: UUID
    status: str = "pending"

    # Complex JSONB fields
    items: list[OrderItem]  # Array of order items
    shipping_address: ShippingAddress  # Nested address object
    billing_info: dict[str, Any]  # Flexible billing information
    metadata: dict[str, Any] = Field(default_factory=dict)  # Order metadata

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = None

    # Computed properties
    @property
    def total_amount(self) -> Decimal:
        """Calculate total order amount."""
        total = Decimal("0")
        for item in self.items:
            item_total = item.unit_price * item.quantity
            # Apply discounts
            for discount in item.discounts:
                if discount["type"] == "percentage":
                    item_total *= 1 - Decimal(str(discount["value"])) / 100
                elif discount["type"] == "fixed":
                    item_total -= Decimal(str(discount["value"]))
            total += max(item_total, Decimal("0"))  # Ensure non-negative
        return total.quantize(Decimal("0.01"))


class Analytics(BaseModel):
    """Analytics data model with time-series JSONB data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    entity_type: str  # "user", "product", "order"
    entity_id: UUID

    # Time-series data in JSONB
    metrics: dict[str, list[dict[str, Any]]]  # {"page_views": [{"timestamp": "...", "value": 100}]}
    aggregates: dict[str, Any]  # Pre-computed aggregates
    tags: list[str] = Field(default_factory=list)

    # Time range
    start_date: datetime
    end_date: datetime

    created_at: datetime = Field(default_factory=datetime.now)


# Repository implementations
class OrderRepository(BaseRepository[Order, UUID]):
    """Repository for order operations with advanced JSONB queries."""

    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="orders",
            model_class=Order,
            primary_key="id",
            # Enable automatic JSON field detection
            auto_detect_json=True,
        )

    async def find_by_customer(self, customer_id: UUID) -> list[Order]:
        """Find all orders for a customer."""
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE customer_id = %s
            ORDER BY created_at DESC
        """

        async with self.db_connection.cursor() as cur:
            await cur.execute(query, [customer_id])
            rows = await cur.fetchall()

            return [self.model_class(**self._postprocess_data(dict(row))) for row in rows]

    async def find_by_product(self, product_id: UUID) -> list[Order]:
        """Find orders containing a specific product using JSONB operators."""
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE items @> %s::jsonb
            ORDER BY created_at DESC
        """

        # Search for product in items array
        search_param = json.dumps([{"product_id": str(product_id)}])

        async with self.db_connection.cursor() as cur:
            await cur.execute(query, [search_param])
            rows = await cur.fetchall()

            return [self.model_class(**self._postprocess_data(dict(row))) for row in rows]

    async def find_by_status_and_date_range(self, status: str, start_date: datetime, end_date: datetime) -> list[Order]:
        """Find orders by status within a date range."""
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE status = %s
            AND created_at BETWEEN %s AND %s
            ORDER BY created_at DESC
        """

        async with self.db_connection.cursor() as cur:
            await cur.execute(query, [status, start_date, end_date])
            rows = await cur.fetchall()

            return [self.model_class(**self._postprocess_data(dict(row))) for row in rows]

    async def update_order_status(self, order_id: UUID, new_status: str) -> Order:
        """Update order status and add to metadata history."""
        # Get current order
        order = await self.get_by_id(order_id)

        # Update metadata with status history
        if "status_history" not in order.metadata:
            order.metadata["status_history"] = []

        order.metadata["status_history"].append(
            {"from": order.status, "to": new_status, "timestamp": datetime.now().isoformat(), "user": "system"}
        )

        # Update order
        return await self.update(
            order_id, {"status": new_status, "metadata": order.metadata, "updated_at": datetime.now()}
        )

    async def aggregate_by_city(self) -> list[dict[str, Any]]:
        """Aggregate orders by shipping city using JSONB operations."""
        query = f"""
            SELECT
                shipping_address->>'city' as city,
                COUNT(*) as order_count,
                SUM(
                    (SELECT SUM((item->>'quantity')::int * (item->>'unit_price')::decimal)
                     FROM jsonb_array_elements(items) as item)
                ) as total_revenue
            FROM {self.table_name}
            GROUP BY shipping_address->>'city'
            ORDER BY order_count DESC
        """

        async with self.db_connection.cursor() as cur:
            await cur.execute(query)
            rows = await cur.fetchall()

            return [
                {
                    "city": row["city"],
                    "order_count": row["order_count"],
                    "total_revenue": float(row["total_revenue"]) if row["total_revenue"] else 0,
                }
                for row in rows
            ]


class AnalyticsRepository(BaseRepository[Analytics, UUID]):
    """Repository for analytics with time-series JSONB operations."""

    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="analytics",
            model_class=Analytics,
            primary_key="id",
            auto_detect_json=True,
        )

    async def append_metric(self, analytics_id: UUID, metric_name: str, value: dict[str, Any]) -> Analytics:
        """Append a new metric value to the time-series data."""
        query = f"""
            UPDATE {self.table_name}
            SET metrics = jsonb_set(
                metrics,
                %s,
                COALESCE(metrics->%s, '[]'::jsonb) || %s::jsonb
            )
            WHERE id = %s
            RETURNING *
        """

        path = f"{{{metric_name}}}"
        value_json = json.dumps(value)

        async with self.db_connection.cursor() as cur:
            await cur.execute(query, [path, metric_name, value_json, analytics_id])
            row = await cur.fetchone()

            if not row:
                raise RecordNotFoundError(f"Analytics {analytics_id} not found")

            return self.model_class(**self._postprocess_data(dict(row)))

    async def query_by_tags(self, tags: list[str]) -> list[Analytics]:
        """Find analytics entries containing all specified tags."""
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE tags @> %s::jsonb
            ORDER BY created_at DESC
        """

        tags_json = json.dumps(tags)

        async with self.db_connection.cursor() as cur:
            await cur.execute(query, [tags_json])
            rows = await cur.fetchall()

            return [self.model_class(**self._postprocess_data(dict(row))) for row in rows]


async def setup_database():
    """Set up database and create tables."""
    settings = DatabaseSettings(
        host="localhost",
        port=5432,
        dbname="psycopg_test",
        user="postgres",
        password="postgres",
        enable_json_adapters=True,
    )

    db = Database(settings)
    await db.init_db()

    async with db.connection() as conn, conn.cursor() as cur:
        # Create orders table
        await cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id UUID PRIMARY KEY,
                    order_number VARCHAR(50) UNIQUE NOT NULL,
                    customer_id UUID NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    items JSONB NOT NULL,
                    shipping_address JSONB NOT NULL,
                    billing_info JSONB NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ
                )
            """)

        # Create indexes for JSONB queries
        await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
                CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
                CREATE INDEX IF NOT EXISTS idx_orders_items ON orders USING GIN(items);
                CREATE INDEX IF NOT EXISTS idx_orders_shipping ON orders USING GIN(shipping_address);
                CREATE INDEX IF NOT EXISTS idx_orders_metadata ON orders USING GIN(metadata);
            """)

        # Create analytics table
        await cur.execute("""
                CREATE TABLE IF NOT EXISTS analytics (
                    id UUID PRIMARY KEY,
                    entity_type VARCHAR(50) NOT NULL,
                    entity_id UUID NOT NULL,
                    metrics JSONB NOT NULL DEFAULT '{}',
                    aggregates JSONB NOT NULL DEFAULT '{}',
                    tags JSONB NOT NULL DEFAULT '[]',
                    start_date TIMESTAMPTZ NOT NULL,
                    end_date TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
            """)

        # Create indexes for analytics
        await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_analytics_entity ON analytics(entity_type, entity_id);
                CREATE INDEX IF NOT EXISTS idx_analytics_tags ON analytics USING GIN(tags);
                CREATE INDEX IF NOT EXISTS idx_analytics_metrics ON analytics USING GIN(metrics);
            """)

    return db


async def demonstrate_complex_operations(db: Database):
    """Demonstrate complex JSONB operations."""

    async with db.connection() as conn:
        order_repo = OrderRepository(conn)
        analytics_repo = AnalyticsRepository(conn)

        # 1. Create orders with complex nested structures
        print("\n1. Creating orders with complex JSONB data...")

        customer_id = uuid4()
        orders = []

        for i in range(3):
            order = Order(
                order_number=f"ORD-2024-{1000 + i}",
                customer_id=customer_id,
                status="pending",
                items=[
                    OrderItem(
                        product_id=uuid4(),
                        name=f"Product {j}",
                        quantity=j + 1,
                        unit_price=Decimal(f"{(j + 1) * 10.99}"),
                        discounts=[{"type": "percentage", "value": 10, "code": "SAVE10"}] if j == 0 else [],
                        metadata={"category": "electronics", "weight": 0.5},
                    )
                    for j in range(2)
                ],
                shipping_address=ShippingAddress(
                    street=f"{100 + i} Main St",
                    city="San Francisco" if i % 2 == 0 else "New York",
                    state="CA" if i % 2 == 0 else "NY",
                    postal_code="94105" if i % 2 == 0 else "10001",
                    country="USA",
                    coordinates={"lat": 37.7749, "lon": -122.4194} if i % 2 == 0 else None,
                ),
                billing_info={
                    "method": "credit_card",
                    "last4": f"{1234 + i}",
                    "billing_address": {
                        "same_as_shipping": i % 2 == 0,
                        "city": "San Francisco" if i % 2 == 0 else "Boston",
                    },
                },
                metadata={
                    "source": "web",
                    "campaign": "summer_sale" if i == 0 else "regular",
                    "notes": ["gift_wrap"] if i == 1 else [],
                },
            )

            created_order = await order_repo.create(order)
            orders.append(created_order)
            print(f"  Created order {created_order.order_number} with total: ${created_order.total_amount}")

        # 2. Bulk operations
        print("\n2. Demonstrating bulk operations...")

        bulk_orders = [
            Order(
                order_number=f"BULK-2024-{2000 + i}",
                customer_id=uuid4(),
                status="processing",
                items=[
                    OrderItem(
                        product_id=uuid4(),
                        name=f"Bulk Product {i}",
                        quantity=10,
                        unit_price=Decimal("5.99"),
                        metadata={"bulk": True},
                    )
                ],
                shipping_address=ShippingAddress(
                    street=f"{i} Bulk Ave", city="Chicago", state="IL", postal_code="60601", country="USA"
                ),
                billing_info={"method": "invoice", "terms": "net30"},
            )
            for i in range(5)
        ]

        created_bulk = await order_repo.create_bulk(bulk_orders)
        print(f"  Created {len(created_bulk)} bulk orders")

        # 3. Transaction handling
        print("\n3. Demonstrating transaction handling...")

        tx_manager = TransactionManager(db)

        try:
            async with tx_manager.transaction() as tx_conn:
                tx_order_repo = OrderRepository(tx_conn)

                # Create order in transaction
                tx_order = Order(
                    order_number="TX-2024-3000",
                    customer_id=customer_id,
                    status="pending",
                    items=[
                        OrderItem(
                            product_id=uuid4(), name="Transaction Product", quantity=1, unit_price=Decimal("99.99")
                        )
                    ],
                    shipping_address=ShippingAddress(
                        street="123 Transaction St", city="Seattle", state="WA", postal_code="98101", country="USA"
                    ),
                    billing_info={"method": "pending"},
                )

                created_tx = await tx_order_repo.create(tx_order)

                # Update status with history
                updated_tx = await tx_order_repo.update_order_status(created_tx.id, "confirmed")

                print(f"  Created and updated order in transaction: {updated_tx.order_number}")

                # Simulate validation failure
                if updated_tx.billing_info.get("method") == "pending":
                    raise ValueError("Billing method not set")

        except ValueError as e:
            print(f"  Transaction rolled back: {e}")

        # 4. Complex queries
        print("\n4. Demonstrating complex JSONB queries...")

        # Find orders by customer
        customer_orders = await order_repo.find_by_customer(customer_id)
        print(f"  Found {len(customer_orders)} orders for customer")

        # Find orders by product
        if orders and orders[0].items:
            product_id = orders[0].items[0].product_id
            product_orders = await order_repo.find_by_product(product_id)
            print(f"  Found {len(product_orders)} orders containing product")

        # Aggregate by city
        city_stats = await order_repo.aggregate_by_city()
        print("  Order aggregation by city:")
        for stat in city_stats[:3]:
            print(f"    {stat['city']}: {stat['order_count']} orders, ${stat['total_revenue']:.2f} revenue")

        # 5. Analytics time-series operations
        print("\n5. Demonstrating analytics time-series operations...")

        # Create analytics entry
        analytics = Analytics(
            entity_type="customer",
            entity_id=customer_id,
            metrics={
                "orders": [{"timestamp": datetime.now().isoformat(), "value": len(customer_orders)}],
                "revenue": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "value": float(sum(o.total_amount for o in customer_orders)),
                    }
                ],
            },
            aggregates={
                "total_orders": len(customer_orders),
                "avg_order_value": float(sum(o.total_amount for o in customer_orders) / len(customer_orders))
                if customer_orders
                else 0,
            },
            tags=["active", "valued_customer"],
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
        )

        created_analytics = await analytics_repo.create(analytics)
        print("  Created analytics entry for customer")

        # Append new metrics
        await analytics_repo.append_metric(
            created_analytics.id,
            "page_views",
            {"timestamp": datetime.now().isoformat(), "value": 42, "page": "/checkout"},
        )
        print("  Appended new metric to time-series data")

        # Query by tags
        tagged_analytics = await analytics_repo.query_by_tags(["active"])
        print(f"  Found {len(tagged_analytics)} analytics entries with 'active' tag")

        # 6. Error handling
        print("\n6. Demonstrating error handling...")

        try:
            # Try to create order with invalid JSON
            bad_order = Order(
                order_number="BAD-ORDER",
                customer_id=customer_id,
                status="invalid",
                items=[],  # Empty items should be validated
                shipping_address=ShippingAddress(
                    street="",  # Invalid empty street
                    city="",
                    state="",
                    postal_code="",
                    country="",
                ),
                billing_info={},
            )
            await order_repo.create(bad_order)
        except Exception as e:
            print(f"  Handled validation error: {type(e).__name__}")

        try:
            # Try to update non-existent order
            await order_repo.update_order_status(uuid4(), "shipped")
        except RecordNotFoundError as e:
            print(f"  Handled not found error: {e}")

        # 7. Performance optimization tips
        print("\n7. Performance optimization tips:")
        print("  - Use GIN indexes for JSONB columns that are frequently queried")
        print("  - Consider jsonb_path_ops for smaller, faster indexes")
        print("  - Use partial indexes for specific query patterns")
        print("  - Denormalize frequently accessed nested data")
        print("  - Use generated columns for computed JSONB values")

        # Clean up
        print("\n8. Cleaning up test data...")
        async with conn.cursor() as cur:
            await cur.execute("TRUNCATE TABLE orders CASCADE")
            await cur.execute("TRUNCATE TABLE analytics CASCADE")
        print("  Test data cleaned up")


async def main():
    """Main entry point."""
    print("Advanced JSONB Operations Example")
    print("=" * 50)

    # Setup database
    db = await setup_database()

    try:
        # Run demonstrations
        await demonstrate_complex_operations(db)

        print("\n" + "=" * 50)
        print("Example completed successfully!")
        print("\nKey takeaways:")
        print("- JSONB fields can store complex nested structures")
        print("- PostgreSQL JSONB operators enable powerful queries")
        print("- Transactions work seamlessly with JSONB data")
        print("- Proper indexing is crucial for performance")
        print("- Error handling ensures data integrity")

    finally:
        # Cleanup
        await db.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
