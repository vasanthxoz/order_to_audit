"""
run_benchmark.py
Executes the full benchmark workflow from the spec and prints expected vs actual results.
Run after seeding: python scripts/run_benchmark.py
"""
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db import fetch_one, fetch_all
from modules import purchases, production, bom as bom_module, sales, billing, dispatch, payments
from modules.inventory import get_item_balance

# ─── Helpers ───────────────────────────────────────────────────────────────────

def resolve_id(table, col, value):
    row = fetch_one(f"SELECT id FROM {table} WHERE {col} = %s", (value,))
    if not row:
        raise RuntimeError(f"Cannot find {table}.{col}={value!r}")
    return row["id"]

def stock(item_type, code_col, code):
    tbl = {
        "RAW_MATERIAL": "raw_materials",
        "PACKAGING_MATERIAL": "packaging_materials",
        "FINISHED_GOOD": "products",
    }[item_type]
    item_id = resolve_id(tbl, code_col, code)
    bal = get_item_balance(item_type, item_id)
    return Decimal(str(bal["current_qty"])) if bal else Decimal("0")

def check(label, expected, actual, unit=""):
    ok = "✅" if abs(expected - actual) < Decimal("0.05") else "❌"
    print(f"  {ok}  {label:<35} Expected: {expected}{unit:>5}   Got: {actual}{unit:>5}")

# ─── Benchmark Steps ───────────────────────────────────────────────────────────

def run_benchmark():
    print("\n" + "="*70)
    print(" ORDER-TO-AUDIT BENCHMARK WORKFLOW")
    print("="*70)

    admin_id = resolve_id("users", "username", "admin")
    salesman_a_id = resolve_id("users", "username", "salesman_a")
    salesman_b_id = resolve_id("users", "username", "salesman_b")
    supervisor_id = resolve_id("users", "username", "supervisor")
    supplier_id = resolve_id("suppliers", "name", "Cauvery Agro Mills")
    flour_id = resolve_id("raw_materials", "code", "RM-FLOUR")
    bom_row = fetch_one("SELECT id FROM bom_headers WHERE is_active = TRUE ORDER BY id LIMIT 1")

    # ── Step 1: Purchase 60 kg Flour @ ₹45/kg ──────────────────────────────────
    print("\n[Step 1] Purchase 60 kg Flour @ ₹45/kg from Cauvery Agro Mills")
    flour_unit_id = fetch_one("SELECT unit_id FROM raw_materials WHERE code='RM-FLOUR'")["unit_id"]
    res1 = purchases.record_purchase(
        supplier_id=supplier_id,
        purchase_date="2026-11-26",
        supplier_invoice_no="CAM-INV-001",
        items=[{"item_type": "RAW_MATERIAL", "item_id": flour_id,
                "qty": Decimal("60"), "rate": Decimal("45"), "gst_rate": Decimal("5")}],
        notes="Benchmark purchase",
        user_id=admin_id,
        username="admin"
    )
    print(f"  Purchase recorded: {res1['purchase_no']}")

    # ── Step 2: Production Run ──────────────────────────────────────────────────
    print("\n[Step 2] Production Run — 40 kg Flour, 10.5 L Oil, 1.2 kg Spice, 188 good packets")
    if not bom_row:
        raise RuntimeError("No active BOM found — ensure seed_database.py created the BOM.")
    bom_id = bom_row["id"]
    oil_id = resolve_id("raw_materials", "code", "RM-OIL")
    spice_id = resolve_id("raw_materials", "code", "RM-SPICE")

    res2 = production.execute_production_run(
        bom_id=bom_id,
        production_date="2026-11-26",
        good_packets=Decimal("188"),
        damaged_pouches=Decimal("6"),
        wastage_qty=Decimal("0"),
        cartons_used=Decimal("9"),
        raw_actuals={
            flour_id: Decimal("40"),
            oil_id: Decimal("10.5"),
            spice_id: Decimal("1.2"),
        },
        overheads=[],
        notes="Benchmark batch",
        user_id=supervisor_id,
        username="supervisor"
    )
    print(f"  Batch: {res2['batch_no']}  |  Yield Var: {res2['yield_variance_pct']}%")
    print(f"  Total Cost: ₹{res2['total_cost']}  |  Cost/Pkt: ₹{res2['cost_per_packet']}")

    # ── Step 3: Sales Order A — 150 pkts for Retailer A (Tamil Nadu) ───────────
    print("\n[Step 3] Salesman A: Order 150 packets for Retailer A (Tamil Nadu)")
    retailer_a_id = resolve_id("customers", "name", "Retailer A")
    murukku_id = resolve_id("products", "sku", "MUR-200")
    res3 = sales.create_sales_order(
        customer_id=retailer_a_id,
        salesman_id=salesman_a_id,
        order_date="2026-11-26",
        items=[{"product_id": murukku_id, "qty_packets": Decimal("150")}],
        remarks="Benchmark order A",
        username="salesman_a"
    )
    print(f"  Order: {res3['order_no']}  Shortage: {res3['has_stock_shortage']}")

    # Admin approves
    sales.verify_and_update_order_status(res3["id"], "Approved", admin_id, "admin")
    print("  Admin approved.")

    # Generate GST Invoice
    inv_res = billing.generate_gst_invoice(res3["id"], "2026-11-26", admin_id, "admin")
    print(f"  Invoice: {inv_res['invoice_no']}  Total: ₹{inv_res['total_amount']}")
    invoice_a_id = inv_res["id"]

    # Dispatch
    dsp = dispatch.dispatch_order(res3["id"], "2026-11-26", "TN59AB1234", "Local Transport", "", "", admin_id, "admin")
    print(f"  Dispatched: {dsp['dispatch_no']}")

    # ── Step 4: Sales Order B — 120 pkts for Distributor B (Karnataka) ─────────
    print("\n[Step 4] Salesman B: Order 120 packets for Distributor B (Karnataka — expect shortage)")
    dist_b_id = resolve_id("customers", "name", "Distributor B")
    res4 = sales.create_sales_order(
        customer_id=dist_b_id,
        salesman_id=salesman_b_id,
        order_date="2026-11-26",
        items=[{"product_id": murukku_id, "qty_packets": Decimal("120")}],
        remarks="Benchmark order B",
        username="salesman_b"
    )
    print(f"  Order: {res4['order_no']}  Shortage warning: {res4['has_stock_shortage']}")
    print(f"  Shortage detail: {res4['shortage_note']}")

    # ── Step 5: Record ₹4,000 Payment from Retailer A ──────────────────────────
    print("\n[Step 5] Record ₹4,000 payment from Retailer A")
    pay_res = payments.record_payment(
        invoice_id=invoice_a_id,
        amount=Decimal("4000"),
        payment_date="2026-11-26",
        payment_mode="UPI",
        reference_no="UPI-BM-001",
        remarks="Benchmark payment",
        user_id=admin_id,
        username="admin"
    )
    print(f"  Payment: {pay_res['payment_no']}  Outstanding: ₹{pay_res['outstanding_amount']}")

    # ── Step 6: Add overheads ₹1,200 Labour + ₹600 Gas/Power ──────────────────
    print("\n[Step 6] Add ₹1,200 Labour + ₹600 Gas/Power overheads to production batch")
    run_id = res2["id"]
    r1 = production.add_production_overhead(run_id, "LABOUR", "Production Labour", Decimal("1200"), admin_id, "admin")
    r2 = production.add_production_overhead(run_id, "GAS_POWER", "LPG Gas & Power", Decimal("600"), admin_id, "admin")
    print(f"  Updated Cost/Pkt: ₹{r2['cost_per_packet']}")

    # ── Results Verification ────────────────────────────────────────────────────
    print("\n" + "─"*70)
    print(" BENCHMARK RESULTS VERIFICATION")
    print("─"*70)
    check("Flour stock (kg)",   Decimal("120"),  stock("RAW_MATERIAL", "code", "RM-FLOUR"),    " kg")
    check("Oil stock (L)",      Decimal("19.5"),  stock("RAW_MATERIAL", "code", "RM-OIL"),     " L")
    check("Spice mix stock (kg)",Decimal("3.8"),  stock("RAW_MATERIAL", "code", "RM-SPICE"),   " kg")
    check("Pouches stock",      Decimal("306"),   stock("PACKAGING_MATERIAL", "code", "PM-POUCH"), " pcs")
    check("Cartons stock",      Decimal("21"),    stock("PACKAGING_MATERIAL", "code", "PM-CARTON"), " pcs")

    fg_stock = stock("FINISHED_GOOD", "sku", "MUR-200")
    check("Finished stock after dispatch", Decimal("88"), fg_stock, " pkts")

    # Variance
    batch = fetch_one("SELECT yield_variance_pct, total_cost, cost_per_packet FROM production_runs WHERE id = %s", (run_id,))
    check("Yield variance (%)", Decimal("-6"),    Decimal(str(batch["yield_variance_pct"])),   "%")

    # Find oil consumption variance — must specify item_type=RAW_MATERIAL
    oil_var = fetch_one(
        """SELECT variance_pct FROM production_consumptions
           WHERE production_run_id = %s AND item_type = 'RAW_MATERIAL' AND item_id = %s""",
        (run_id, oil_id)
    )
    if oil_var:
        check("Oil variance (%)",   Decimal("5"), Decimal(str(oil_var["variance_pct"])), "%")

    # Invoice figures
    inv = fetch_one("SELECT * FROM invoices WHERE id = %s", (invoice_a_id,))
    check("Taxable amount (₹)",  Decimal("7500"),   Decimal(str(inv["taxable_amount"])),   " ₹")
    check("CGST amount (₹)",     Decimal("187.50"), Decimal(str(inv["cgst_amount"])),      " ₹")
    check("SGST amount (₹)",     Decimal("187.50"), Decimal(str(inv["sgst_amount"])),      " ₹")
    check("Invoice total (₹)",   Decimal("7875"),   Decimal(str(inv["total_amount"])),     " ₹")
    check("Outstanding (₹)",     Decimal("3875"),   Decimal(str(inv["outstanding_amount"])), " ₹")

    # Costing
    check("Production cost (₹)", Decimal("5855"),  Decimal(str(batch["total_cost"])),        " ₹")
    check("Cost per packet (₹)", Decimal("31.14"),  Decimal(str(batch["cost_per_packet"])).quantize(Decimal("0.01")), " ₹")

    # Margin
    sell_price = Decimal("50")
    cpp = Decimal(str(batch["cost_per_packet"])).quantize(Decimal("0.01"))
    margin = (sell_price - cpp).quantize(Decimal("0.01"))
    check("Margin per packet (₹)", Decimal("18.86"), margin, " ₹")

    print("\n[Benchmark] Complete! Check any ❌ marks above for discrepancies.")
    print("="*70)


if __name__ == "__main__":
    run_benchmark()
