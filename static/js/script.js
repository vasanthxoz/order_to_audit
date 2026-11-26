function addOrderRow() {
    const tbody = document.getElementById("order-items-body");
    if (!tbody) return;
    const firstRow = tbody.querySelector("tr");
    const clone = firstRow.cloneNode(true);
    clone.querySelectorAll("input").forEach(inp => {
        if (inp.type === "number") inp.value = "";
        else inp.value = "";
    });
    clone.querySelectorAll("select").forEach(sel => sel.selectedIndex = 0);
    const warn = clone.querySelector(".stock-warning-cell");
    if (warn) warn.innerHTML = "";
    tbody.appendChild(clone);
}

async function onOrderProductChange(selectEl) {
    const row = selectEl.closest("tr");
    const productId = selectEl.value;
    const priceInput = row.querySelector(".unit-price-display");
    const stockSpan = row.querySelector(".avail-stock-display");
    if (!productId) {
        if (priceInput) priceInput.value = "";
        if (stockSpan) stockSpan.textContent = "-";
        return;
    }
    try {
        const resp = await fetch(`/api/product-price/${productId}`);
        if (!resp.ok) return;
        const data = await resp.json();
        if (priceInput) priceInput.value = data.selling_price.toFixed(2);
        if (stockSpan) {
            stockSpan.textContent = `${data.available_qty} pkt`;
            stockSpan.dataset.avail = data.available_qty;
        }
        checkRowStock(row);
    } catch (e) {
        console.error(e);
    }
}

function checkRowStock(row) {
    const qtyInput = row.querySelector(".qty-input");
    const stockSpan = row.querySelector(".avail-stock-display");
    const warnCell = row.querySelector(".stock-warning-cell");
    if (!qtyInput || !stockSpan || !warnCell) return;
    const qty = parseFloat(qtyInput.value || "0");
    const avail = parseFloat(stockSpan.dataset.avail || "0");
    if (qty > avail && qty > 0) {
        const shortage = (qty - avail).toFixed(0);
        warnCell.innerHTML = `<span class="badge bg-danger">Shortage: ${shortage} pkt</span>`;
    } else if (qty > 0) {
        warnCell.innerHTML = `<span class="badge bg-success">In Stock</span>`;
    } else {
        warnCell.innerHTML = "";
    }
}

function filterTable(inputId, tableId) {
    const filter = (document.getElementById(inputId)?.value || "").toLowerCase();
    const rows = document.querySelectorAll(`#${tableId} tbody tr`);
    rows.forEach(r => {
        r.style.display = r.innerText.toLowerCase().includes(filter) ? "" : "none";
    });
}
