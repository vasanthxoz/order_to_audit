-- Order-to-Audit Management System PostgreSQL Schema
-- No JSON/JSONB columns; pure relational tables with NUMERIC precision.

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(40) UNIQUE NOT NULL,
    description VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(60) UNIQUE NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    phone VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    role_id INTEGER NOT NULL REFERENCES roles(id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS units (
    id SERIAL PRIMARY KEY,
    code VARCHAR(16) UNIQUE NOT NULL,
    name VARCHAR(50) NOT NULL,
    base_unit_code VARCHAR(16) NOT NULL,
    conversion_factor NUMERIC(14,6) NOT NULL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    customer_type VARCHAR(40) NOT NULL DEFAULT 'Retailer',
    gstin VARCHAR(20),
    state VARCHAR(80) NOT NULL,
    state_code VARCHAR(10) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(120),
    address TEXT,
    credit_limit NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    gstin VARCHAR(20),
    state VARCHAR(80) NOT NULL,
    state_code VARCHAR(10) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(120),
    address TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(40) UNIQUE NOT NULL,
    name VARCHAR(150) NOT NULL,
    category VARCHAR(60) NOT NULL,
    pack_size_grams NUMERIC(10,2) NOT NULL,
    pack_label VARCHAR(40) NOT NULL,
    packets_per_carton INTEGER NOT NULL DEFAULT 20,
    hsn_code VARCHAR(20) NOT NULL,
    gst_rate NUMERIC(5,2) NOT NULL DEFAULT 5.00,
    unit_id INTEGER NOT NULL REFERENCES units(id),
    reorder_level NUMERIC(14,3) NOT NULL DEFAULT 20.000,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS price_lists (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    customer_type VARCHAR(40) NOT NULL DEFAULT 'ALL',
    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS price_list_items (
    id SERIAL PRIMARY KEY,
    price_list_id INTEGER NOT NULL REFERENCES price_lists(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    selling_price NUMERIC(12,2) NOT NULL CHECK (selling_price >= 0),
    UNIQUE (price_list_id, product_id)
);

CREATE TABLE IF NOT EXISTS raw_materials (
    id SERIAL PRIMARY KEY,
    code VARCHAR(40) UNIQUE NOT NULL,
    name VARCHAR(150) NOT NULL,
    unit_id INTEGER NOT NULL REFERENCES units(id),
    hsn_code VARCHAR(20),
    gst_rate NUMERIC(5,2) NOT NULL DEFAULT 5.00,
    reorder_level NUMERIC(14,3) NOT NULL DEFAULT 10.000,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS packaging_materials (
    id SERIAL PRIMARY KEY,
    code VARCHAR(40) UNIQUE NOT NULL,
    name VARCHAR(150) NOT NULL,
    unit_id INTEGER NOT NULL REFERENCES units(id),
    hsn_code VARCHAR(20),
    gst_rate NUMERIC(5,2) NOT NULL DEFAULT 18.00,
    reorder_level NUMERIC(14,3) NOT NULL DEFAULT 50.000,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS inventory_balances (
    id SERIAL PRIMARY KEY,
    item_type VARCHAR(30) NOT NULL CHECK (item_type IN ('RAW_MATERIAL', 'PACKAGING_MATERIAL', 'FINISHED_GOOD')),
    item_id INTEGER NOT NULL,
    unit_id INTEGER NOT NULL REFERENCES units(id),
    opening_qty NUMERIC(14,3) NOT NULL DEFAULT 0.000,
    current_qty NUMERIC(14,3) NOT NULL DEFAULT 0.000 CHECK (current_qty >= 0),
    weighted_avg_rate NUMERIC(14,4) NOT NULL DEFAULT 0.0000,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (item_type, item_id)
);

CREATE TABLE IF NOT EXISTS stock_ledger (
    id SERIAL PRIMARY KEY,
    movement_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    item_type VARCHAR(30) NOT NULL CHECK (item_type IN ('RAW_MATERIAL', 'PACKAGING_MATERIAL', 'FINISHED_GOOD')),
    item_id INTEGER NOT NULL,
    movement_type VARCHAR(30) NOT NULL CHECK (movement_type IN ('OPENING', 'RECEIPT', 'ISSUE', 'PRODUCTION_IN', 'DISPATCH_OUT', 'ADJUSTMENT')),
    qty_in NUMERIC(14,3) NOT NULL DEFAULT 0.000,
    qty_out NUMERIC(14,3) NOT NULL DEFAULT 0.000,
    unit_rate NUMERIC(14,4) NOT NULL DEFAULT 0.0000,
    total_value NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    balance_qty NUMERIC(14,3) NOT NULL DEFAULT 0.000,
    source_doc_type VARCHAR(40) NOT NULL,
    source_doc_id INTEGER,
    source_doc_no VARCHAR(60),
    remarks TEXT,
    user_id INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchases (
    id SERIAL PRIMARY KEY,
    purchase_no VARCHAR(40) UNIQUE NOT NULL,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    purchase_date DATE NOT NULL DEFAULT CURRENT_DATE,
    supplier_invoice_no VARCHAR(60),
    subtotal NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    gst_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    total_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    notes TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchase_items (
    id SERIAL PRIMARY KEY,
    purchase_id INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
    item_type VARCHAR(30) NOT NULL CHECK (item_type IN ('RAW_MATERIAL', 'PACKAGING_MATERIAL')),
    item_id INTEGER NOT NULL,
    qty NUMERIC(14,3) NOT NULL CHECK (qty > 0),
    rate NUMERIC(14,4) NOT NULL CHECK (rate >= 0),
    gst_rate NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    line_total NUMERIC(14,2) NOT NULL DEFAULT 0.00
);

CREATE TABLE IF NOT EXISTS bom_headers (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    version VARCHAR(20) NOT NULL DEFAULT 'v1.0',
    batch_name VARCHAR(120) NOT NULL,
    expected_output_packets NUMERIC(14,3) NOT NULL CHECK (expected_output_packets > 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bom_items (
    id SERIAL PRIMARY KEY,
    bom_id INTEGER NOT NULL REFERENCES bom_headers(id) ON DELETE CASCADE,
    item_type VARCHAR(30) NOT NULL CHECK (item_type IN ('RAW_MATERIAL', 'PACKAGING_MATERIAL')),
    item_id INTEGER NOT NULL,
    standard_qty NUMERIC(14,3) NOT NULL CHECK (standard_qty >= 0),
    unit_id INTEGER NOT NULL REFERENCES units(id)
);

CREATE TABLE IF NOT EXISTS production_runs (
    id SERIAL PRIMARY KEY,
    batch_no VARCHAR(40) UNIQUE NOT NULL,
    bom_id INTEGER NOT NULL REFERENCES bom_headers(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    production_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expected_packets NUMERIC(14,3) NOT NULL,
    good_packets NUMERIC(14,3) NOT NULL CHECK (good_packets >= 0),
    damaged_pouches NUMERIC(14,3) NOT NULL DEFAULT 0.000 CHECK (damaged_pouches >= 0),
    wastage_qty NUMERIC(14,3) NOT NULL DEFAULT 0.000 CHECK (wastage_qty >= 0),
    cartons_used NUMERIC(14,3) NOT NULL DEFAULT 0.000 CHECK (cartons_used >= 0),
    yield_variance_pct NUMERIC(8,2) NOT NULL DEFAULT 0.00,
    yield_abnormal BOOLEAN NOT NULL DEFAULT FALSE,
    material_cost NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    packaging_cost NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    overhead_cost NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    total_cost NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    cost_per_packet NUMERIC(12,4) NOT NULL DEFAULT 0.0000,
    status VARCHAR(30) NOT NULL DEFAULT 'COMPLETED',
    notes TEXT,
    supervisor_id INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS production_consumptions (
    id SERIAL PRIMARY KEY,
    production_run_id INTEGER NOT NULL REFERENCES production_runs(id) ON DELETE CASCADE,
    item_type VARCHAR(30) NOT NULL CHECK (item_type IN ('RAW_MATERIAL', 'PACKAGING_MATERIAL')),
    item_id INTEGER NOT NULL,
    planned_qty NUMERIC(14,3) NOT NULL DEFAULT 0.000,
    actual_qty NUMERIC(14,3) NOT NULL DEFAULT 0.000,
    damaged_qty NUMERIC(14,3) NOT NULL DEFAULT 0.000,
    unit_rate NUMERIC(14,4) NOT NULL DEFAULT 0.0000,
    total_cost NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    variance_pct NUMERIC(8,2) NOT NULL DEFAULT 0.00,
    is_abnormal BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS production_overheads (
    id SERIAL PRIMARY KEY,
    production_run_id INTEGER NOT NULL REFERENCES production_runs(id) ON DELETE CASCADE,
    expense_type VARCHAR(40) NOT NULL CHECK (expense_type IN ('LABOUR', 'GAS_POWER', 'OTHER')),
    description VARCHAR(200),
    amount NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sales_orders (
    id SERIAL PRIMARY KEY,
    order_no VARCHAR(40) UNIQUE NOT NULL,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    salesman_id INTEGER NOT NULL REFERENCES users(id),
    order_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status VARCHAR(30) NOT NULL DEFAULT 'Submitted' CHECK (status IN ('Submitted', 'Approved', 'Rejected', 'Invoiced', 'Dispatched')),
    subtotal NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    gst_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    total_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    has_stock_shortage BOOLEAN NOT NULL DEFAULT FALSE,
    shortage_note TEXT,
    remarks TEXT,
    verified_by INTEGER REFERENCES users(id),
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sales_order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES sales_orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty_packets NUMERIC(14,3) NOT NULL CHECK (qty_packets > 0),
    unit_price NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
    gst_rate NUMERIC(5,2) NOT NULL DEFAULT 5.00,
    taxable_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    gst_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    line_total NUMERIC(14,2) NOT NULL DEFAULT 0.00
);

CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    invoice_no VARCHAR(40) UNIQUE NOT NULL,
    financial_year VARCHAR(16) NOT NULL,
    order_id INTEGER UNIQUE NOT NULL REFERENCES sales_orders(id),
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    invoice_date DATE NOT NULL DEFAULT CURRENT_DATE,
    place_of_supply VARCHAR(100) NOT NULL,
    supply_type VARCHAR(20) NOT NULL CHECK (supply_type IN ('INTRA_STATE', 'INTER_STATE')),
    taxable_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    cgst_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    sgst_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    igst_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    total_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    paid_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    outstanding_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    status VARCHAR(20) NOT NULL DEFAULT 'POSTED' CHECK (status IN ('POSTED', 'CANCELLED')),
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    hsn_code VARCHAR(20) NOT NULL,
    qty_packets NUMERIC(14,3) NOT NULL,
    unit_price NUMERIC(12,2) NOT NULL,
    taxable_amount NUMERIC(14,2) NOT NULL,
    gst_rate NUMERIC(5,2) NOT NULL,
    cgst_rate NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    cgst_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    sgst_rate NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    sgst_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    igst_rate NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    igst_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    line_total NUMERIC(14,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS credit_notes (
    id SERIAL PRIMARY KEY,
    credit_note_no VARCHAR(40) UNIQUE NOT NULL,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    credit_date DATE NOT NULL DEFAULT CURRENT_DATE,
    reason TEXT NOT NULL,
    taxable_amount NUMERIC(14,2) NOT NULL,
    cgst_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    sgst_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    igst_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    total_amount NUMERIC(14,2) NOT NULL,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dispatches (
    id SERIAL PRIMARY KEY,
    dispatch_no VARCHAR(40) UNIQUE NOT NULL,
    order_id INTEGER UNIQUE NOT NULL REFERENCES sales_orders(id),
    invoice_id INTEGER UNIQUE NOT NULL REFERENCES invoices(id),
    dispatch_date DATE NOT NULL DEFAULT CURRENT_DATE,
    vehicle_no VARCHAR(40),
    transporter VARCHAR(100),
    lr_no VARCHAR(60),
    remarks TEXT,
    dispatched_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    payment_no VARCHAR(40) UNIQUE NOT NULL,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    payment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    amount NUMERIC(14,2) NOT NULL CHECK (amount > 0),
    payment_mode VARCHAR(30) NOT NULL DEFAULT 'UPI',
    reference_no VARCHAR(80),
    remarks TEXT,
    recorded_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS system_settings (
    key VARCHAR(80) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    username VARCHAR(80),
    action VARCHAR(60) NOT NULL,
    entity_type VARCHAR(60) NOT NULL,
    entity_id INTEGER,
    details TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stock_ledger_item ON stock_ledger(item_type, item_id, movement_date);
CREATE INDEX IF NOT EXISTS idx_sales_orders_status ON sales_orders(status, order_date);
CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_id, status, invoice_date);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id, created_at);
