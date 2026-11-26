# Order-to-Audit Management System

A complete, production-ready web application for a South Indian snacks manufacturer
(Murukku, Mixture, Chips & Sweets) integrating the entire order-to-audit workflow.

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend   | Python 3.13 · Flask 3.x |
| Database  | PostgreSQL 19 |
| DB Driver | psycopg2-binary |
| Auth      | Flask-Login + Werkzeug password hashing |
| Charts    | Chart.js 4.x (CDN) |
| PDF       | ReportLab 5.x |
| Excel     | Openpyxl 3.x |
| Frontend  | Bootstrap 5.3 · Vanilla JS |

---

## Quick Start

### 1. Configure Database Credentials

Copy `.env.example` to `.env` and set your PostgreSQL password:

```bash
cp .env.example .env
# Edit .env — set DB_PASSWORD to your Postgres password
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Create & Migrate Database

```bash
python scripts/setup_database.py
```

### 4. Seed Master Data & Benchmark Opening Stock

```bash
python scripts/seed_database.py
```

### 5. Run the Benchmark Workflow (optional verification)

```bash
python scripts/run_benchmark.py
```

### 6. Start the Application

```bash
python app.py
```
Open `http://localhost:5000` in your browser.

---

## Demo Login Credentials

| Username     | Password   | Role                    |
|-------------|------------|------------------------|
| `admin`     | `admin123` | Admin (full access)     |
| `salesman_a`| `sales123` | Salesman A              |
| `salesman_b`| `sales123` | Salesman B              |
| `supervisor`| `prod123`  | Production Supervisor   |
| `auditor`   | `audit123` | Auditor (read-only)     |
| `owner`     | `owner123` | Owner (executive dashboard)|

---

## Folder Structure

```
order_to_audit/
├── app.py                  ← Flask app + all routes
├── config.py               ← Config loaded from .env
├── db.py                   ← PostgreSQL connection helpers
├── requirements.txt
├── .env / .env.example
├── database/
│   ├── schema.sql          ← All relational tables + indexes
│   ├── seed.sql            ← Master data (roles, products, materials, customers)
│   └── queries.sql         ← Reference SQL queries
├── modules/
│   ├── auth.py             ← User authentication + Flask-Login
│   ├── masters.py          ← Customers, suppliers, products, materials
│   ├── inventory.py        ← Stock balances + immutable stock ledger (WAC)
│   ├── purchases.py        ← Purchase recording + stock receipt
│   ├── bom.py              ← Bill of Materials CRUD
│   ├── production.py       ← Production runs, consumption, overhead costing
│   ├── variance.py         ← Variance % calculation + tolerance flagging
│   ├── costing.py          ← Cost per packet + margin summary
│   ├── sales.py            ← Sales orders, stock check, approval workflow
│   ├── gst.py              ← CGST/SGST/IGST split (intra/inter state)
│   ├── billing.py          ← GST invoice generation + credit notes
│   ├── dispatch.py         ← Order dispatch + finished goods deduction
│   ├── payments.py         ← Full/partial payment recording + ageing
│   ├── reports.py          ← All report queries + export dataset builder
│   ├── dashboard.py        ← Owner KPI aggregations
│   ├── admin.py            ← Admin summary counts
│   └── audit.py            ← Audit log recording + retrieval
├── utils/
│   ├── validators.py       ← Input validation helpers
│   ├── decorators.py       ← @role_required decorator
│   ├── unit_conversion.py  ← kg/g, L/ml, pkt/ctn conversions
│   ├── pdf_generator.py    ← ReportLab invoice & report PDFs
│   ├── excel_export.py     ← Openpyxl XLSX export
│   └── csv_export.py       ← UTF-8 CSV export
├── templates/              ← Jinja2 HTML templates (Bootstrap 5)
├── static/                 ← CSS, JS, images
├── scripts/
│   ├── setup_database.py   ← Create DB + apply schema
│   ├── seed_database.py    ← Seed master data + benchmark opening stock
│   └── run_benchmark.py    ← Execute & verify full benchmark workflow
└── tests/
    ├── test_gst.py         ← GST split unit tests
    ├── test_production.py  ← Variance calculation unit tests
    ├── test_inventory.py   ← WAC valuation unit tests
    └── test_benchmark.py   ← Integration tests (benchmark results)
```

---

## Database Design

### Costing Method
**Weighted Average Cost (WAC)**: On every material receipt, the new average rate is recomputed as:
```
New Average Rate = (Old Qty × Old Rate + New Qty × New Rate) / (Old Qty + New Qty)
```
Issues use the current weighted average rate. The rate never changes on issue — only on receipt.

### Inventory Ledger
- `inventory_balances` — holds one row per item with current_qty and weighted_avg_rate.
- `stock_ledger` — append-only immutable ledger. Direct updates to current_qty are NEVER allowed;
  all movements go through `record_stock_movement()` which atomically updates both tables
  inside a PostgreSQL transaction.

### Variance Formula
```
Variance (%) = ((Actual − Planned) / Planned) × 100
```
Configured tolerance: **±3%** (adjustable in `system_settings` table).
Variances beyond tolerance are flagged `is_abnormal = TRUE`.

### GST Logic
- **Intra-state** (factory Tamil Nadu → customer Tamil Nadu): CGST = GST/2, SGST = GST/2
- **Inter-state** (factory Tamil Nadu → any other state): IGST = full GST rate
- Invoice cancellation via **Credit Notes** only — invoices are never deleted.

---

## Benchmark Results (Expected vs Actual)

| Parameter | Expected Result |
|-----------|----------------|
| Flour stock | 120 kg |
| Oil stock | 19.5 L |
| Spice mix stock | 3.8 kg |
| Pouches stock | 306 |
| Cartons stock | 21 |
| Finished stock after production | 238 |
| Finished stock after dispatch | 88 |
| Yield variance | −6% (Abnormal) |
| Oil variance | +5% (Abnormal) |
| Taxable amount | ₹7,500 |
| CGST | ₹187.50 |
| SGST | ₹187.50 |
| Invoice total | ₹7,875 |
| Outstanding | ₹3,875 |
| Distributor B shortage | 32 packets |
| Production cost | ₹5,855 |
| Cost per packet | ₹31.14 |
| Margin per packet | ₹18.86 |

---

## Running Tests

```bash
python -m pytest tests/ -v
```

---

## Security Features
- Passwords hashed with Werkzeug `generate_password_hash` (PBKDF2-SHA256)
- Parameterized SQL queries throughout — no string interpolation
- Role-based access control via `@role_required` decorator
- Audit log on every invoice, production, and payment change
- Database transactions prevent partial writes / race conditions on stock

---

## Assumptions
1. All financial calculations use Python `Decimal` and PostgreSQL `NUMERIC` — no floating point.
2. Opening stock is set via `seed_database.py` as a `OPENING` ledger entry.
3. Production costs (overheads) can be added after the run; cost/packet is recalculated automatically.
4. Inter-state supply is determined by comparing customer state to factory state (Tamil Nadu).
5. One carton = 20 packets (configurable per product via `packets_per_carton`).
