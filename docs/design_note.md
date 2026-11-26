# ER Diagram & Design Notes

## Entity-Relationship Summary

```
roles ──< users >── sales_orders >── sales_order_items >── products
                                                         └── price_list_items
customers ──< sales_orders ──< invoices ──< invoice_items
                                      └──< credit_notes
                                      └──< dispatches
                                      └──< payments

suppliers ──< purchases >── purchase_items

bom_headers >── bom_items
     │              └── raw_materials / packaging_materials
     └──< production_runs >── production_consumptions
                           └── production_overheads

inventory_balances (1 row per item) ←── stock_ledger (append-only)
```

## Key Design Decisions

### Inventory Model
- Single `inventory_balances` table holds live balance per item (all categories).
- `stock_ledger` is immutable — never updated, only inserted. 
- Closing stock = sum of ledger movements, not a stored column.

### Production Costing
1. Material cost = Σ (actual_qty × weighted_avg_rate) per raw material
2. Packaging cost = Σ (actual_qty × weighted_avg_rate) per packaging material
3. Overhead cost = Σ labour + gas/power + other
4. Total cost = material + packaging + overhead
5. Cost per packet = total_cost / good_packets

### GST Invoice Numbering
Format: `INV/{FY}/{SEQUENCE}` e.g. `INV/2026-27/0001`
Financial year determined from invoice date (Apr–Mar).
