-- Same logic as src/inventory_analyzer.py, written in SQL (SQLite).
-- Input table: inventory (loaded from data/inventory.csv)
WITH metrics AS (
    SELECT
        product_id, supplier, stock, on_order, daily_demand, lead_time_days,
        safety_stock, unit_cost, moq,
        stock + on_order                                     AS inventory_position,
        ROUND(daily_demand * lead_time_days, 2)              AS lead_time_demand
    FROM inventory
),
levels AS (
    SELECT *,
        ROUND(lead_time_demand + safety_stock, 2)            AS reorder_point,
        ROUND(daily_demand * 30 + safety_stock, 2)           AS target_stock
    FROM metrics
),
classified AS (
    SELECT *,
        CASE
            WHEN inventory_position < lead_time_demand  THEN 'URGENT'
            WHEN inventory_position <= reorder_point    THEN 'REORDER'
            ELSE 'OK'
        END                                                  AS status,
        ROUND(target_stock - inventory_position, 2)          AS gap
    FROM levels
),
batches AS (
    SELECT *,
        gap * 1.0 / moq                                      AS exact_batches
    FROM classified
),
orders AS (
    SELECT *,
        CASE
            WHEN status <> 'OK' AND gap > 0
            THEN (CAST(exact_batches AS INTEGER)
                  + (exact_batches > CAST(exact_batches AS INTEGER))) * moq
            ELSE 0
        END                                                  AS order_qty
    FROM batches
),
valued AS (
    SELECT *,
        ROUND(order_qty * unit_cost, 2)                      AS est_cost,
        daily_demand * 365 * unit_cost                       AS annual_value
    FROM orders
),
ranked AS (
    SELECT *,
        SUM(annual_value) OVER (
            ORDER BY annual_value DESC, product_id
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        )                                                    AS value_before,
        SUM(annual_value) OVER ()                            AS total_value
    FROM valued
)
SELECT
    product_id, supplier, stock, on_order, daily_demand, lead_time_days,
    safety_stock, unit_cost, moq,
    inventory_position, lead_time_demand, reorder_point, target_stock,
    status, gap, order_qty, est_cost, annual_value,
    CASE
        WHEN COALESCE(value_before, 0) * 1.0 / NULLIF(total_value, 0) < 0.80 THEN 'A'
        WHEN COALESCE(value_before, 0) * 1.0 / NULLIF(total_value, 0) < 0.95 THEN 'B'
        ELSE 'C'
    END                                                      AS abc_class
FROM ranked
ORDER BY
    CASE status WHEN 'URGENT' THEN 0 WHEN 'REORDER' THEN 1 ELSE 2 END,
    product_id;