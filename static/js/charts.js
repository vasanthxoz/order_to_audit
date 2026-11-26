function renderBarChart(canvasId, labels, values, labelText, color) {
    const ctx = document.getElementById(canvasId);
    if (!ctx || typeof Chart === "undefined") return;
    new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [{
                label: labelText,
                data: values,
                backgroundColor: color || "rgba(99, 102, 241, 0.85)",
                borderRadius: 8,
                borderSkipped: false,
                maxBarThickness: 48
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "#0f172a",
                    padding: 10,
                    cornerRadius: 8
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: {
                    beginAtZero: true,
                    grid: { color: "#f1f5f9" }
                }
            }
        }
    });
}

function renderDoughnutChart(canvasId, labels, values) {
    const ctx = document.getElementById(canvasId);
    if (!ctx || typeof Chart === "undefined") return;
    new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: ["#6366f1", "#10b981", "#f59e0b", "#3b82f6", "#8b5cf6"],
                borderWidth: 2,
                borderColor: "#ffffff"
            }]
        },
        options: {
            responsive: true,
            cutout: "66%",
            plugins: {
                legend: {
                    position: "bottom",
                    labels: { usePointStyle: true, padding: 16 }
                }
            }
        }
    });
}
