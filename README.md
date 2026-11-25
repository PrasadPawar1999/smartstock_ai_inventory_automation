

# SmartStock AI: Inventory Reorder Tool

A Python tool that reads inventory and supplier data, works out which products will run out before the next delivery arrives, and recommends what to order, how much, and what it will cost. It recommends only. A person reviews every order.

I built it as a portfolio project for supply chain, inventory and procurement analyst roles.

## The problem

A company with hundreds of products has to decide, for each one, when to reorder and how much. Order too late and the product runs out. Order too much and cash is tied up in stock. Each supplier also has a delivery time (lead time) and a minimum order quantity (MOQ), which makes the decision harder to do by eye.

## What it does

- Reads `data/inventory.csv` and checks the data before using it
- Labels every product `OK`, `REORDER` or `URGENT`
- Calculates reorder point, target stock, days of cover, order quantity (rounded up to the supplier's MOQ) and estimated cost
- Ranks products by ABC class (annual consumption value)
- Writes a prioritised report to `reports/reorder_report.csv`
- Produces the same report from a SQL query, and checks that both versions agree

## Results on the sample data (990 products)

| Status | Products |
|---|---|
| OK | 850 |
| REORDER | 57 |
| URGENT | 83 |

- Total estimated purchase cost: **96,376.40**
- ABC classes: A = 440 products (80.1% of annual value), B = 288 (15.0%), C = 262 (5.0%)
- 48 of the 83 urgent products are class A, so those are the first to review

| ABC class | OK | REORDER | URGENT |
|---|---|---|---|
| A | 358 | 34 | 48 |
| B | 251 | 14 | 23 |
| C | 241 | 9 | 12 |

## The rules

```
Inventory position = stock + on_order
Lead-time demand   = daily_demand x lead_time_days
Reorder point      = lead-time demand + safety_stock
Target stock       = daily_demand x 30 + safety_stock
Gap                = target stock - inventory position
Order quantity     = round the gap up to a multiple of MOQ
Estimated cost     = order quantity x unit_cost
Days of cover      = stock / daily_demand
Annual value       = daily_demand x 365 x unit_cost
```

**Status**

| Status | Rule |
|---|---|
| URGENT | inventory position is below lead-time demand (it will run out before delivery) |
| REORDER | inventory position is at or below the reorder point, but not urgent |
| OK | everything else |

**Ordering:** an order is only recommended when the status is URGENT or REORDER and the gap is positive. Healthy products get no order, even if they are below the 30-day target.

**Zero demand:** the reorder point equals the safety stock. The product is only reordered if its position falls to the safety stock or below. Days of cover is left empty and written as `n/a`, because dividing by zero has no meaningful answer.

**ABC class:** products are ranked by annual value. A product is class A if the value ranked above it is still under 80% of the total, B if under 95%, and C otherwise. Products with zero demand are class C.

### Worked example

Product `10-626-8536`: stock 17, nothing on order, demand 5.4 per day, lead time 10 days, safety stock 11, MOQ 50, unit cost 5.00.

- Lead-time demand = 5.4 x 10 = 54, and the position is only 17, so the status is **URGENT**
- Target stock = 5.4 x 30 + 11 = 173, so the gap is 156
- 156 / 50 = 3.12, rounded up to 4 batches = **200 units**
- Estimated cost = 200 x 5.00 = **1,000.00**

## Data validation

The program refuses to produce a report if the input has any of these problems, and lists every problem it found with the row number:

- A required column is missing
- Empty values or text (such as "7 days") in a number column
- Negative stock, on-order, demand, lead time or safety stock
- Unit cost or MOQ of zero or below
- Duplicate or missing product ID
- Missing supplier

The folder `tests/bad_data/` holds six deliberately broken files, and the tests check that each one is rejected.

## How I checked it

1. **By hand first.** I calculated five products in Excel (`docs/hand_calculations.xlsx`), covering URGENT, REORDER, OK, zero stock and zero demand, including a product sitting exactly on its reorder point.
2. **Automated tests.** 45 tests with pytest check the status rules, the boundary cases, MOQ rounding, the zero-demand rule, the five hand-calculated products, every validation rule and the totals on the full dataset.
3. **Two implementations.** `sql/reorder_report.sql` does the same job in SQLite. `src/sql_report.py` compares it with the Python output and reports a match on all 990 products.
4. **Excel pivot tables** (`docs/abc_analysis.xlsx`) give the same ABC counts and the same 96,376.40 total.

One thing I found along the way: SQLite and numpy round an exact half (such as 2491.125) in different directions, so 10 products differed by 0.01 in annual value. Since the ABC class does not need rounded values, I stopped rounding that column and the two versions then matched exactly.

![pytest results](docs/pytest_results.png)

## Project structure

```
smartstock-ai-inventory-automation/
├── data/
│   ├── products.csv            # source product list
│   └── inventory.csv           # generated input for the tool
├── src/
│   ├── build_inventory.py      # builds inventory.csv from products.csv
│   ├── validation.py           # data checks
│   ├── inventory_analyzer.py   # the engine
│   ├── sql_report.py           # runs the SQL version and compares
│   └── make_bad_samples.py     # creates the broken test files
├── sql/
│   └── reorder_report.sql
├── tests/
│   ├── test_inventory.py
│   ├── test_extras.py
│   └── bad_data/
├── reports/
│   ├── reorder_report.csv
│   └── reorder_report_sql.csv
├── docs/                       # hand calculations, ABC pivots, screenshots
├── dashboard/                  # Excel dashboard
├── pytest.ini
├── requirements.txt
└── README.md
```

## Where the data comes from

The tool needs columns that public datasets do not have, so part of the data is simulated.

- **Real (from the source product list):** product ID, category, unit cost, current stock. TODO: add the source name and link here.
- **Simulated by `src/build_inventory.py`** with a fixed random seed (42), so it produces the same file every time: supplier, lead time, MOQ, daily demand, safety stock, on-order quantity and product name. There are 15 fictional suppliers, two per category, and each supplier has its own lead time and MOQ.
- A few rows are set up on purpose as edge cases: zero stock and zero demand.

None of this is real company data, and the results should be read as a demonstration of the method.

## How to run it

Windows (PowerShell):

```
git clone https://github.com/PrasadPawar1999/smartstock_ai_inventory_automation.git
cd smartstock_ai_inventory_automation
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

python src/build_inventory.py       # creates data/inventory.csv
python src/inventory_analyzer.py    # creates reports/reorder_report.csv
python src/sql_report.py            # runs the SQL version and compares
pytest                              # runs the 45 tests
```

On Mac or Linux, activate the environment with `source venv/bin/activate` and use `python3`.

To run the tool on your own file, pass its path: `python src/inventory_analyzer.py path/to/file.csv`. It needs these columns: `product_id`, `supplier`, `stock`, `on_order`, `daily_demand`, `lead_time_days`, `safety_stock`, `unit_cost`, `moq`.

## Dashboard

An Excel dashboard in `dashboard/smartstock_dashboard.xlsx` shows the headline numbers (products, products needing action, urgent items, estimated purchase cost and urgent class A items), with charts and a table of items needing attention. Every total reconciles with the Python report. TODO: add a dashboard screenshot here and update this section when the dashboard is finished.

## Limitations

- The data is partly simulated, as described above.
- Demand is treated as a constant daily rate. There is no seasonality, forecasting or demand variability, and safety stock is an input, not calculated.
- The 30-day target is a simplification. If a supplier's lead time is longer than 30 days, the target stock can fall below the reorder point, so a REORDER product could end up with an order of 0. Real planning would set the target from lead time plus a review period.
- Open purchase orders are handled as a single `on_order` number. Delivery dates are not modelled.
- With randomly spread demand, class A holds 44% of the products. Real data is usually much more concentrated.
- The expiration dates in the source file are not used, and all of them are in the past.
- One location only. The tool recommends orders and does not place them.

## Ideas for later

- A visual workflow that runs the report and drafts supplier emails for human review
- Safety stock calculated from demand variability
- Expiry-aware ordering for perishable products
- A Power BI version of the dashboard

The parameters here (lead time, safety stock, MOQ, reorder point) are the same concepts used by ERP and MRP systems such as SAP, which is what I wanted to understand by building them from scratch.

## Author

Prasad Pawar. TODO: add your LinkedIn link.
