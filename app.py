from datetime import date
from decimal import Decimal
from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from io import BytesIO

from config import Config
from utils.decorators import role_required
from utils.validators import to_decimal, require_non_empty, validate_gstin
from utils.pdf_generator import generate_invoice_pdf, generate_report_pdf
from utils.excel_export import generate_excel_bytes
from utils.csv_export import generate_csv_bytes

from modules import auth, masters, inventory, purchases, bom, production, variance, costing, sales, billing, dispatch, payments, reports, dashboard, admin, audit

app = Flask(__name__)
app.config.from_object(Config)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return auth.load_user_by_id(user_id)


@app.context_processor
def inject_globals():
    return {"factory_name": Config.FACTORY_NAME, "factory_state": Config.FACTORY_STATE, "today_str": date.today().isoformat()}


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user = auth.authenticate_user(username, password)
        if user:
            login_user(user)
            flash(f"Welcome back, {user.full_name} ({user.role_name}).", "success")
            return redirect(url_for("index"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    role_map = {
        "admin": "admin_dashboard",
        "salesman": "salesman_dashboard",
        "production_supervisor": "production_dashboard",
        "auditor": "auditor_dashboard",
        "owner": "owner_dashboard",
    }
    return redirect(url_for(role_map.get(current_user.role_name, "owner_dashboard")))


@app.route("/dashboard/admin")
@login_required
@role_required("admin", "owner")
def admin_dashboard():
    summary = admin.get_admin_summary()
    low_stock = inventory.get_low_stock_alerts()
    recent_orders = sales.list_orders()[:8]
    return render_template("admin_dashboard.html", summary=summary, low_stock=low_stock, recent_orders=recent_orders)


@app.route("/dashboard/salesman")
@login_required
@role_required("salesman", "admin", "owner")
def salesman_dashboard():
    my_orders = sales.list_orders(salesman_id=current_user.id if current_user.role_name == "salesman" else None)
    cust_sales = reports.get_customer_wise_sales(salesman_id=current_user.id if current_user.role_name == "salesman" else None)
    return render_template("salesman_dashboard.html", orders=my_orders, cust_sales=cust_sales)


@app.route("/dashboard/production")
@login_required
@role_required("production_supervisor", "admin", "owner")
def production_dashboard():
    runs = production.list_production_runs()[:8]
    low_stock = inventory.get_low_stock_alerts()
    tol = variance.get_tolerance_pct()
    return render_template("production_dashboard.html", runs=runs, low_stock=low_stock, tolerance=tol)


@app.route("/dashboard/auditor")
@login_required
@role_required("auditor", "admin", "owner")
def auditor_dashboard():
    gst_rows = reports.get_gst_summary()
    ageing = payments.get_outstanding_and_ageing()
    logs = audit.get_audit_logs(limit=15)
    return render_template("auditor_dashboard.html", gst_rows=gst_rows, ageing=ageing, logs=logs)


@app.route("/dashboard/owner")
@login_required
@role_required("owner", "admin")
def owner_dashboard():
    data = dashboard.get_owner_dashboard_data()
    low_stock = inventory.get_low_stock_alerts()
    return render_template("owner_dashboard.html", data=data, low_stock=low_stock)


@app.route("/users", methods=["GET", "POST"])
@login_required
@role_required("admin")
def users_page():
    if request.method == "POST":
        try:
            auth.create_user(
                require_non_empty(request.form.get("username"), "Username"),
                require_non_empty(request.form.get("full_name"), "Full name"),
                require_non_empty(request.form.get("email"), "Email"),
                request.form.get("phone", ""),
                require_non_empty(request.form.get("password"), "Password"),
                request.form.get("role_id"),
            )
            flash("User created successfully.", "success")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("users_page"))
    return render_template("users.html", users=auth.list_users(), roles=auth.list_roles())


@app.route("/customers", methods=["GET", "POST"])
@login_required
@role_required("admin", "salesman", "owner")
def customers_page():
    if request.method == "POST":
        try:
            masters.create_customer(
                require_non_empty(request.form.get("name"), "Customer name"),
                request.form.get("customer_type", "Retailer"),
                validate_gstin(request.form.get("gstin")),
                require_non_empty(request.form.get("state"), "State"),
                require_non_empty(request.form.get("state_code"), "State code"),
                request.form.get("phone", ""),
                request.form.get("email", ""),
                request.form.get("address", ""),
                request.form.get("credit_limit", 0),
            )
            flash("Customer added successfully.", "success")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("customers_page"))
    return render_template("customers.html", customers=masters.list_customers())


@app.route("/suppliers", methods=["GET", "POST"])
@login_required
@role_required("admin", "production_supervisor", "owner")
def suppliers_page():
    if request.method == "POST":
        try:
            masters.create_supplier(
                require_non_empty(request.form.get("name"), "Supplier name"),
                validate_gstin(request.form.get("gstin")),
                require_non_empty(request.form.get("state"), "State"),
                require_non_empty(request.form.get("state_code"), "State code"),
                request.form.get("phone", ""),
                request.form.get("email", ""),
                request.form.get("address", ""),
            )
            flash("Supplier added successfully.", "success")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("suppliers_page"))
    return render_template("suppliers.html", suppliers=masters.list_suppliers())


@app.route("/products", methods=["GET", "POST"])
@login_required
@role_required("admin", "owner", "salesman", "production_supervisor", "auditor")
def products_page():
    if request.method == "POST" and current_user.role_name in ("admin", "owner"):
        try:
            masters.create_product(
                require_non_empty(request.form.get("sku"), "SKU"),
                require_non_empty(request.form.get("name"), "Product name"),
                require_non_empty(request.form.get("category"), "Category"),
                to_decimal(request.form.get("pack_size_grams"), "Pack size", min_value=1),
                require_non_empty(request.form.get("pack_label"), "Pack label"),
                int(request.form.get("packets_per_carton", 20)),
                require_non_empty(request.form.get("hsn_code"), "HSN code"),
                to_decimal(request.form.get("gst_rate"), "GST rate", min_value=0),
                request.form.get("unit_id"),
                to_decimal(request.form.get("selling_price"), "Selling price", min_value=0),
                to_decimal(request.form.get("reorder_level", 20), "Reorder level", min_value=0),
            )
            flash("Product added successfully.", "success")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("products_page"))
    return render_template("products.html", products=masters.list_products(), units=masters.list_units())


@app.route("/raw-materials", methods=["GET", "POST"])
@login_required
@role_required("admin", "production_supervisor", "owner", "auditor")
def raw_materials_page():
    if request.method == "POST" and current_user.role_name in ("admin", "production_supervisor"):
        try:
            masters.create_raw_material(
                require_non_empty(request.form.get("code"), "Code"),
                require_non_empty(request.form.get("name"), "Name"),
                request.form.get("unit_id"),
                request.form.get("hsn_code", ""),
                to_decimal(request.form.get("gst_rate", 5), "GST rate", min_value=0),
                to_decimal(request.form.get("reorder_level", 10), "Reorder level", min_value=0),
            )
            flash("Raw material added.", "success")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("raw_materials_page"))
    return render_template("raw_materials.html", materials=masters.list_raw_materials(), units=masters.list_units())


@app.route("/packaging-materials", methods=["GET", "POST"])
@login_required
@role_required("admin", "production_supervisor", "owner", "auditor")
def packaging_materials_page():
    if request.method == "POST" and current_user.role_name in ("admin", "production_supervisor"):
        try:
            masters.create_packaging_material(
                require_non_empty(request.form.get("code"), "Code"),
                require_non_empty(request.form.get("name"), "Name"),
                request.form.get("unit_id"),
                request.form.get("hsn_code", ""),
                to_decimal(request.form.get("gst_rate", 18), "GST rate", min_value=0),
                to_decimal(request.form.get("reorder_level", 50), "Reorder level", min_value=0),
            )
            flash("Packaging material added.", "success")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("packaging_materials_page"))
    return render_template("packaging_materials.html", materials=masters.list_packaging_materials(), units=masters.list_units())


@app.route("/api/product-price/<int:product_id>")
@login_required
def api_product_price(product_id):
    info = masters.get_product_selling_price(product_id)
    bal = inventory.get_item_balance("FINISHED_GOOD", product_id)
    if not info:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "selling_price": float(info["selling_price"] or 0),
        "gst_rate": float(info["gst_rate"] or 0),
        "available_qty": float(bal["current_qty"] if bal else 0),
    })


@app.route("/orders")
@login_required
def orders_page():
    salesman_filter = current_user.id if current_user.role_name == "salesman" else None
    status_filter = request.args.get("status") or None
    return render_template("orders.html", orders=sales.list_orders(salesman_id=salesman_filter, status=status_filter))


@app.route("/orders/create", methods=["GET", "POST"])
@login_required
@role_required("salesman", "admin")
def create_order_page():
    if request.method == "POST":
        try:
            customer_id = request.form.get("customer_id")
            order_date = request.form.get("order_date") or date.today().isoformat()
            remarks = request.form.get("remarks", "")
            product_ids = request.form.getlist("product_id[]")
            qtys = request.form.getlist("qty_packets[]")
            items = []
            for pid, q in zip(product_ids, qtys):
                if pid and q and Decimal(str(q)) > 0:
                    items.append({"product_id": int(pid), "qty_packets": to_decimal(q, "Quantity", min_value=1, allow_zero=False)})
            res = sales.create_sales_order(customer_id, current_user.id, order_date, items, remarks, current_user.username)
            if res["has_stock_shortage"]:
                flash(f"Order {res['order_no']} submitted with STOCK SHORTAGE WARNING: {res['shortage_note']}", "warning")
            else:
                flash(f"Order {res['order_no']} submitted successfully.", "success")
            return redirect(url_for("orders_page"))
        except Exception as e:
            flash(str(e), "danger")
    return render_template("create_order.html", customers=masters.list_customers(), products=masters.list_products())


@app.route("/orders/<int:order_id>/approve", methods=["GET", "POST"])
@login_required
@role_required("admin", "owner")
def approve_order_page(order_id):
    details = sales.get_order_details(order_id)
    if not details:
        flash("Order not found.", "danger")
        return redirect(url_for("orders_page"))
    if request.method == "POST":
        action = request.form.get("action")
        remarks = request.form.get("remarks", "")
        try:
            if action == "approve":
                sales.verify_and_update_order_status(order_id, "Approved", current_user.id, current_user.username, remarks)
                flash("Order approved.", "success")
            elif action == "reject":
                sales.verify_and_update_order_status(order_id, "Rejected", current_user.id, current_user.username, remarks)
                flash("Order rejected.", "info")
            elif action == "invoice":
                inv = billing.generate_gst_invoice(order_id, date.today(), current_user.id, current_user.username)
                flash(f"GST Invoice {inv['invoice_no']} generated (Rs. {inv['total_amount']}).", "success")
                return redirect(url_for("invoice_detail_page", invoice_id=inv["id"]))
            return redirect(url_for("approve_order_page", order_id=order_id))
        except Exception as e:
            flash(str(e), "danger")
    return render_template("approve_order.html", order=details["order"], items=details["items"])


@app.route("/purchases", methods=["GET", "POST"])
@login_required
@role_required("admin", "production_supervisor", "owner", "auditor")
def purchases_page():
    if request.method == "POST" and current_user.role_name in ("admin", "production_supervisor"):
        try:
            item_types = request.form.getlist("item_type[]")
            item_ids = request.form.getlist("item_id[]")
            qtys = request.form.getlist("qty[]")
            rates = request.form.getlist("rate[]")
            gst_rates = request.form.getlist("gst_rate[]")
            items = []
            for it_type, it_id, q, r, g in zip(item_types, item_ids, qtys, rates, gst_rates):
                if it_type and it_id and q:
                    items.append({
                        "item_type": it_type,
                        "item_id": int(it_id),
                        "qty": to_decimal(q, "Quantity", min_value=0.001, allow_zero=False),
                        "rate": to_decimal(r, "Rate", min_value=0),
                        "gst_rate": to_decimal(g or 0, "GST %", min_value=0),
                    })
            res = purchases.record_purchase(
                request.form.get("supplier_id"),
                request.form.get("purchase_date") or date.today().isoformat(),
                request.form.get("supplier_invoice_no", ""),
                items,
                request.form.get("notes", ""),
                current_user.id,
                current_user.username,
            )
            flash(f"Purchase {res['purchase_no']} recorded and stock updated.", "success")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("purchases_page"))
    return render_template(
        "purchases.html",
        purchases=purchases.list_purchases(),
        suppliers=masters.list_suppliers(),
        raw_materials=masters.list_raw_materials(),
        packaging_materials=masters.list_packaging_materials(),
    )


@app.route("/bom", methods=["GET", "POST"])
@login_required
@role_required("admin", "production_supervisor", "owner", "auditor")
def bom_page():
    if request.method == "POST" and current_user.role_name in ("admin", "production_supervisor"):
        try:
            item_types = request.form.getlist("item_type[]")
            item_ids = request.form.getlist("item_id[]")
            std_qtys = request.form.getlist("standard_qty[]")
            unit_ids = request.form.getlist("unit_id[]")
            items = []
            for t, i, q, u in zip(item_types, item_ids, std_qtys, unit_ids):
                if t and i and q:
                    items.append({"item_type": t, "item_id": int(i), "standard_qty": to_decimal(q, "Standard Qty", min_value=0.001), "unit_id": int(u)})
            bom.create_bom(
                request.form.get("product_id"),
                request.form.get("version", "v1.0"),
                require_non_empty(request.form.get("batch_name"), "Batch name"),
                to_decimal(request.form.get("expected_output_packets"), "Expected output", min_value=1),
                items,
                current_user.id,
            )
            flash("BOM created successfully.", "success")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("bom_page"))

    boms_list = [bom.get_bom_with_items(b["id"]) for b in bom.list_boms()]
    return render_template(
        "bom.html",
        boms=boms_list,
        products=masters.list_products(),
        raw_materials=masters.list_raw_materials(),
        packaging_materials=masters.list_packaging_materials(),
        units=masters.list_units(),
    )


@app.route("/production", methods=["GET", "POST"])
@login_required
@role_required("admin", "production_supervisor", "owner", "auditor")
def production_page():
    if request.method == "POST" and current_user.role_name in ("admin", "production_supervisor"):
        action = request.form.get("action", "create_run")
        try:
            if action == "add_overhead":
                res = production.add_production_overhead(
                    request.form.get("production_run_id"),
                    request.form.get("expense_type", "LABOUR"),
                    request.form.get("description", ""),
                    to_decimal(request.form.get("amount"), "Amount", min_value=0.01, allow_zero=False),
                    current_user.id,
                    current_user.username,
                )
                flash(f"Overhead added. Updated Cost/Packet: Rs. {res['cost_per_packet']:.2f}", "success")
            else:
                bom_id = int(request.form.get("bom_id"))
                bom_data = bom.get_bom_with_items(bom_id)
                raw_actuals = {}
                for it in bom_data["bom_items"]:
                    if it["item_type"] == "RAW_MATERIAL":
                        val = request.form.get(f"raw_actual_{it['item_id']}")
                        raw_actuals[it["item_id"]] = to_decimal(val, it["item_name"], min_value=0)
                overheads = []
                labour_amt = Decimal(str(request.form.get("labour_cost") or 0))
                gas_amt = Decimal(str(request.form.get("gas_power_cost") or 0))
                if labour_amt > 0:
                    overheads.append({"expense_type": "LABOUR", "description": "Production labour", "amount": labour_amt})
                if gas_amt > 0:
                    overheads.append({"expense_type": "GAS_POWER", "description": "Gas and power", "amount": gas_amt})

                res = production.execute_production_run(
                    bom_id=bom_id,
                    production_date=request.form.get("production_date") or date.today().isoformat(),
                    good_packets=to_decimal(request.form.get("good_packets"), "Good packets", min_value=1, allow_zero=False),
                    damaged_pouches=to_decimal(request.form.get("damaged_pouches", 0), "Damaged pouches", min_value=0),
                    wastage_qty=to_decimal(request.form.get("wastage_qty", 0), "Wastage", min_value=0),
                    cartons_used=to_decimal(request.form.get("cartons_used", 0), "Cartons used", min_value=0),
                    raw_actuals=raw_actuals,
                    overheads=overheads,
                    notes=request.form.get("notes", ""),
                    user_id=current_user.id,
                    username=current_user.username,
                )
                flash(f"Batch {res['batch_no']} completed! Cost/Packet: Rs. {res['cost_per_packet']:.2f}", "success")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("production_page"))

    boms_full = [bom.get_bom_with_items(b["id"]) for b in bom.list_boms()]
    return render_template("production.html", runs=production.list_production_runs(), boms=boms_full)


@app.route("/variance")
@login_required
def variance_page():
    return render_template(
        "variance.html",
        runs=reports.get_production_variance_report(),
        details=reports.get_material_variance_details(),
        tolerance=variance.get_tolerance_pct(),
    )


@app.route("/inventory")
@login_required
def inventory_page():
    item_type = request.args.get("type") or None
    return render_template("inventory.html", stock=inventory.get_stock_summary(item_type), selected_type=item_type)


@app.route("/stock-ledger")
@login_required
def stock_ledger_page():
    item_type = request.args.get("type") or None
    return render_template("stock_ledger.html", ledger=inventory.get_stock_ledger(item_type), selected_type=item_type)


@app.route("/invoices")
@login_required
def invoices_page():
    return render_template("invoice.html", invoices=billing.list_invoices(), detail=None)


@app.route("/invoices/<int:invoice_id>")
@login_required
def invoice_detail_page(invoice_id):
    detail = billing.get_invoice_details(invoice_id)
    if not detail:
        flash("Invoice not found.", "danger")
        return redirect(url_for("invoices_page"))
    return render_template("invoice.html", invoices=billing.list_invoices(), detail=detail)


@app.route("/invoices/<int:invoice_id>/pdf")
@login_required
def invoice_pdf(invoice_id):
    detail = billing.get_invoice_details(invoice_id)
    if not detail:
        flash("Invoice not found.", "danger")
        return redirect(url_for("invoices_page"))
    pdf_bytes = generate_invoice_pdf(detail["invoice"], detail["items"], detail["customer"])
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{detail['invoice']['invoice_no'].replace('/', '_')}.pdf",
    )


@app.route("/credit-notes", methods=["GET", "POST"])
@login_required
@role_required("admin", "auditor", "owner")
def credit_notes_page():
    if request.method == "POST" and current_user.role_name == "admin":
        try:
            res = billing.cancel_invoice_with_credit_note(
                request.form.get("invoice_id"),
                require_non_empty(request.form.get("reason"), "Cancellation reason"),
                current_user.id,
                current_user.username,
            )
            flash(f"Invoice cancelled via Credit Note {res['credit_note_no']}.", "warning")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("credit_notes_page"))
    posted_invoices = [i for i in billing.list_invoices() if i["status"] == "POSTED"]
    return render_template("credit_note.html", credit_notes=billing.list_credit_notes(), posted_invoices=posted_invoices)


@app.route("/dispatch", methods=["GET", "POST"])
@login_required
@role_required("admin", "production_supervisor", "owner")
def dispatch_page():
    if request.method == "POST" and current_user.role_name in ("admin", "production_supervisor"):
        try:
            res = dispatch.dispatch_order(
                request.form.get("order_id"),
                request.form.get("dispatch_date") or date.today().isoformat(),
                request.form.get("vehicle_no", ""),
                request.form.get("transporter", ""),
                request.form.get("lr_no", ""),
                request.form.get("remarks", ""),
                current_user.id,
                current_user.username,
            )
            flash(f"Order dispatched ({res['dispatch_no']}) and finished stock reduced.", "success")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("dispatch_page"))
    ready_orders = sales.list_orders(status="Invoiced")
    return render_template("dispatch.html", dispatches=dispatch.list_dispatches(), ready_orders=ready_orders)


@app.route("/payments", methods=["GET", "POST"])
@login_required
@role_required("admin", "auditor", "owner")
def payments_page():
    if request.method == "POST" and current_user.role_name == "admin":
        try:
            res = payments.record_payment(
                request.form.get("invoice_id"),
                to_decimal(request.form.get("amount"), "Payment amount", min_value=0.01, allow_zero=False),
                request.form.get("payment_date") or date.today().isoformat(),
                request.form.get("payment_mode", "UPI"),
                request.form.get("reference_no", ""),
                request.form.get("remarks", ""),
                current_user.id,
                current_user.username,
            )
            flash(f"Payment {res['payment_no']} recorded. Remaining balance: Rs. {res['outstanding_amount']:.2f}", "success")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("payments_page"))
    open_invoices = [i for i in billing.list_invoices() if i["status"] == "POSTED" and Decimal(str(i["outstanding_amount"])) > 0]
    return render_template("payments.html", payments=payments.list_payments(), open_invoices=open_invoices)


@app.route("/outstanding")
@login_required
def outstanding_page():
    return render_template("outstanding.html", ageing=payments.get_outstanding_and_ageing())


@app.route("/costing")
@login_required
def costing_page():
    return render_template("costing.html", costings=costing.get_costing_summary())


@app.route("/reports")
@login_required
def reports_page():
    start_date = request.args.get("start_date") or None
    end_date = request.args.get("end_date") or None
    return render_template(
        "reports.html",
        start_date=start_date or "",
        end_date=end_date or "",
        sales_register=reports.get_sales_register(start_date, end_date),
        customer_sales=reports.get_customer_wise_sales(start_date, end_date),
        product_sales=reports.get_product_wise_sales(start_date, end_date),
        gst_summary=reports.get_gst_summary(start_date, end_date),
    )


@app.route("/reports/export/<report_type>/<fmt>")
@login_required
def export_report(report_type, fmt):
    start_date = request.args.get("start_date") or None
    end_date = request.args.get("end_date") or None
    title, headers, rows = reports.build_export_dataset(report_type, start_date, end_date)
    if fmt == "csv":
        data = generate_csv_bytes(headers, rows)
        return send_file(BytesIO(data), mimetype="text/csv", as_attachment=True, download_name=f"{report_type}.csv")
    if fmt == "xlsx":
        data = generate_excel_bytes(title, headers, rows)
        return send_file(
            BytesIO(data),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"{report_type}.xlsx",
        )
    if fmt == "pdf":
        sub = f"Period: {start_date or 'All'} to {end_date or 'All'}"
        data = generate_report_pdf(title, headers, rows, subtitle=sub)
        return send_file(BytesIO(data), mimetype="application/pdf", as_attachment=True, download_name=f"{report_type}.pdf")
    flash("Unsupported export format.", "danger")
    return redirect(url_for("reports_page"))


@app.route("/audit-logs")
@login_required
@role_required("admin", "auditor", "owner")
def audit_logs_page():
    return render_template("audit_logs.html", logs=audit.get_audit_logs(limit=250))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
