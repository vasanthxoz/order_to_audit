from decimal import Decimal, ROUND_HALF_UP
from db import fetch_all


def get_costing_summary():
    """Return per-batch costing with selling price before GST, cost per packet (2dp), and margin."""
    rows = fetch_all(
        """
        SELECT pr.id, pr.batch_no, pr.production_date, p.name AS product_name, p.sku,
               pr.expected_packets, pr.good_packets,
               pr.material_cost, pr.packaging_cost, pr.overhead_cost, pr.total_cost,
               pr.cost_per_packet,
               COALESCE(pli.selling_price, 0) AS selling_price
        FROM production_runs pr
        JOIN products p ON p.id = pr.product_id
        LEFT JOIN price_lists pl ON pl.is_default = TRUE AND pl.is_active = TRUE
        LEFT JOIN price_list_items pli ON pli.price_list_id = pl.id AND pli.product_id = p.id
        ORDER BY pr.production_date DESC, pr.id DESC
        """
    )
    result = []
    for r in rows:
        cpp = Decimal(str(r["cost_per_packet"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sp = Decimal(str(r["selling_price"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        margin = (sp - cpp).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        item = dict(r)
        item["cost_per_packet_2dp"] = cpp
        item["selling_price_2dp"] = sp
        item["margin_per_packet"] = margin
        result.append(item)
    return result
