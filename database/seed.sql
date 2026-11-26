-- Seed data for Order-to-Audit Management System (Benchmark + Master Data)

INSERT INTO roles (name, description) VALUES
    ('admin', 'System administrator: order verification, invoicing, dispatch, payments, masters'),
    ('salesman', 'Field salesman: mobile-friendly order entry and customer sales view'),
    ('production_supervisor', 'Production supervisor: BOM, material receipts/issues, production runs, wastage'),
    ('auditor', 'Accountant/Auditor: read-only access to reports, ledgers, and exports'),
    ('owner', 'Business owner: executive dashboard, variance, costing, and receivables')
ON CONFLICT (name) DO NOTHING;

INSERT INTO units (code, name, base_unit_code, conversion_factor) VALUES
    ('kg', 'Kilogram', 'g', 1000.000000),
    ('g', 'Gram', 'g', 1.000000),
    ('L', 'Litre', 'ml', 1000.000000),
    ('ml', 'Millilitre', 'ml', 1.000000),
    ('pcs', 'Pieces', 'pcs', 1.000000),
    ('pkt', 'Packets', 'pkt', 1.000000),
    ('ctn', 'Cartons', 'pkt', 20.000000)
ON CONFLICT (code) DO NOTHING;

INSERT INTO system_settings (key, value, description) VALUES
    ('variance_tolerance_pct', '3.0', 'Abnormal variance threshold percentage (+/-)'),
    ('financial_year', '2026-27', 'Active Indian financial year for invoice numbering')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

-- Products
INSERT INTO products (sku, name, category, pack_size_grams, pack_label, packets_per_carton, hsn_code, gst_rate, unit_id, reorder_level)
SELECT 'MUR-200', 'Murukku 200 g', 'Murukku', 200.00, '200 g', 20, '21069099', 5.00, id, 30.000 FROM units WHERE code = 'pkt'
ON CONFLICT (sku) DO NOTHING;

INSERT INTO products (sku, name, category, pack_size_grams, pack_label, packets_per_carton, hsn_code, gst_rate, unit_id, reorder_level)
SELECT 'MIX-200', 'Madras Mixture 200 g', 'Mixture', 200.00, '200 g', 20, '21069099', 5.00, id, 25.000 FROM units WHERE code = 'pkt'
ON CONFLICT (sku) DO NOTHING;

INSERT INTO products (sku, name, category, pack_size_grams, pack_label, packets_per_carton, hsn_code, gst_rate, unit_id, reorder_level)
SELECT 'CHP-200', 'Banana Chips 200 g', 'Chips', 200.00, '200 g', 20, '21069099', 12.00, id, 20.000 FROM units WHERE code = 'pkt'
ON CONFLICT (sku) DO NOTHING;

INSERT INTO products (sku, name, category, pack_size_grams, pack_label, packets_per_carton, hsn_code, gst_rate, unit_id, reorder_level)
SELECT 'SWT-250', 'Mysore Pak 250 g', 'Sweets', 250.00, '250 g', 16, '21069099', 5.00, id, 15.000 FROM units WHERE code = 'pkt'
ON CONFLICT (sku) DO NOTHING;

-- Price List
INSERT INTO price_lists (name, customer_type, is_default, is_active)
VALUES ('Standard Wholesale & Retail', 'ALL', TRUE, TRUE)
ON CONFLICT (name) DO NOTHING;

INSERT INTO price_list_items (price_list_id, product_id, selling_price)
SELECT pl.id, p.id, v.price
FROM price_lists pl
JOIN (VALUES
    ('MUR-200', 50.00),
    ('MIX-200', 55.00),
    ('CHP-200', 65.00),
    ('SWT-250', 95.00)
) AS v(sku, price) ON TRUE
JOIN products p ON p.sku = v.sku
WHERE pl.name = 'Standard Wholesale & Retail'
ON CONFLICT (price_list_id, product_id) DO NOTHING;

-- Raw Materials
INSERT INTO raw_materials (code, name, unit_id, hsn_code, gst_rate, reorder_level)
SELECT 'RM-FLOUR', 'Flour', id, '11029090', 5.00, 40.000 FROM units WHERE code = 'kg'
ON CONFLICT (code) DO NOTHING;

INSERT INTO raw_materials (code, name, unit_id, hsn_code, gst_rate, reorder_level)
SELECT 'RM-OIL', 'Oil', id, '15119090', 5.00, 15.000 FROM units WHERE code = 'L'
ON CONFLICT (code) DO NOTHING;

INSERT INTO raw_materials (code, name, unit_id, hsn_code, gst_rate, reorder_level)
SELECT 'RM-SPICE', 'Salt and spice mix', id, '09109990', 5.00, 2.000 FROM units WHERE code = 'kg'
ON CONFLICT (code) DO NOTHING;

-- Packaging Materials
INSERT INTO packaging_materials (code, name, unit_id, hsn_code, gst_rate, reorder_level)
SELECT 'PM-POUCH', 'Pouches', id, '39232100', 18.00, 100.000 FROM units WHERE code = 'pcs'
ON CONFLICT (code) DO NOTHING;

INSERT INTO packaging_materials (code, name, unit_id, hsn_code, gst_rate, reorder_level)
SELECT 'PM-CARTON', 'Cartons', id, '48191010', 18.00, 15.000 FROM units WHERE code = 'pcs'
ON CONFLICT (code) DO NOTHING;

-- Customers
INSERT INTO customers (name, customer_type, gstin, state, state_code, phone, email, address, credit_limit)
SELECT 'Retailer A', 'Retailer', '33AAACR1111A1Z1', 'Tamil Nadu', '33', '9842100001', 'retailera@example.com', '12 West Masi Street, Madurai, Tamil Nadu', 50000.00
WHERE NOT EXISTS (SELECT 1 FROM customers WHERE name = 'Retailer A');

INSERT INTO customers (name, customer_type, gstin, state, state_code, phone, email, address, credit_limit)
SELECT 'Distributor B', 'Distributor', '29AAACD2222B1Z2', 'Karnataka', '29', '9845000002', 'distributorb@example.com', '44 Chickpet Main Road, Bengaluru, Karnataka', 100000.00
WHERE NOT EXISTS (SELECT 1 FROM customers WHERE name = 'Distributor B');

-- Suppliers
INSERT INTO suppliers (name, gstin, state, state_code, phone, email, address)
SELECT 'Cauvery Agro Mills', '33AAACC3333C1Z3', 'Tamil Nadu', '33', '9443100011', 'sales@cauveryagro.com', 'Trichy Road, Thanjavur, Tamil Nadu'
WHERE NOT EXISTS (SELECT 1 FROM suppliers WHERE name = 'Cauvery Agro Mills');

INSERT INTO suppliers (name, gstin, state, state_code, phone, email, address)
SELECT 'Kongu Packaging Industries', '33AAACK4444D1Z4', 'Tamil Nadu', '33', '9443200022', 'orders@kongupack.com', 'Avinashi Road, Coimbatore, Tamil Nadu'
WHERE NOT EXISTS (SELECT 1 FROM suppliers WHERE name = 'Kongu Packaging Industries');
