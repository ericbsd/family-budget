let categoryChart = null;
let trendChart    = null;

/* ── Navigate to transactions filtered by category + period ────── */
function periodUrl(categoryId, year, month) {
    const pad   = String(month).padStart(2, '0');
    const start = `${year}-${pad}-01`;
    const end   = new Date(year, month, 0).toISOString().slice(0, 10);
    return `/transactions?category_id=${categoryId}&start_date=${start}&end_date=${end}`;
}

/* ── Theme-aware chart colours ────────────────────────────────── */
function chartTheme() {
    const dark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
    return {
        text: dark ? '#dee2e6' : '#212529',
        grid: dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
    };
}

/* ── Month / year selector init ───────────────────────────────── */
const MONTH_NAMES = ['January','February','March','April','May','June',
                     'July','August','September','October','November','December'];

let _periods = [];   // [{year, month}, …] sorted newest first

async function initSelectors() {
    const mSel = document.getElementById('monthSelect');
    const ySel = document.getElementById('yearSelect');

    try {
        const res = await charts.periods();
        _periods  = res.data;
    } catch (e) {
        _periods  = [];
    }

    if (!_periods.length) {
        // No data at all — fall back to current month/year
        const now = new Date();
        ySel.innerHTML = `<option value="${now.getFullYear()}">${now.getFullYear()}</option>`;
        mSel.innerHTML = `<option value="${now.getMonth()+1}">${MONTH_NAMES[now.getMonth()]}</option>`;
        return;
    }

    // Populate year selector with years that have data
    const years = [...new Set(_periods.map(p => p.year))].sort((a, b) => b - a);
    ySel.innerHTML = years.map(y => `<option value="${y}">${y}</option>`).join('');

    // Populate months for the selected (most recent) year
    _updateMonthSelector();

    // When year changes, refresh month options and reload
    ySel.addEventListener('change', () => {
        _updateMonthSelector();
        loadDashboard();
    });
}

function _updateMonthSelector() {
    const year = parseInt(document.getElementById('yearSelect').value);
    const mSel = document.getElementById('monthSelect');
    const months = _periods.filter(p => p.year === year)
                           .map(p => p.month)
                           .sort((a, b) => b - a);   // newest first

    mSel.innerHTML = months.map(m =>
        `<option value="${m}">${MONTH_NAMES[m - 1]}</option>`
    ).join('');
}

function selectedPeriod() {
    return {
        year:  parseInt(document.getElementById('yearSelect').value),
        month: parseInt(document.getElementById('monthSelect').value),
    };
}

/* ── Load everything ──────────────────────────────────────────── */
async function loadDashboard() {
    const { year, month } = selectedPeriod();
    await Promise.all([
        loadSummaryCards(year, month),
        loadCategoryChart(year, month),
        loadBudgetStatus(year, month),
        loadTrendChart(year),
        loadTopMerchants(year, month),
    ]);
}

/* ── Summary cards ────────────────────────────────────────────── */
async function loadSummaryCards(year, month) {
    try {
        const pad   = String(month).padStart(2, '0');
        const start = `${year}-${pad}-01`;
        const end   = new Date(year, month, 0).toISOString().slice(0, 10);

        const [monthlyRes, allRes, uncatRes] = await Promise.all([
            charts.monthly(year, month),
            transactions.list({ start_date: start, end_date: end, limit: 2000 }),
            transactions.list({ category_id: 0, limit: 1 }),
        ]);

        let spent = 0, income = 0, count = 0;
        monthlyRes.data.forEach(d => { spent += Math.abs(d.total) || 0; count += d.count || 0; });
        (allRes.data || []).forEach(t => { if (t.amount > 0) income += t.amount; });

        document.getElementById('totalSpent').textContent  = formatAmount(spent);
        document.getElementById('totalIncome').textContent = formatAmount(income);
        document.getElementById('txCount').textContent     = count;
        document.getElementById('uncatCount').textContent  = uncatRes.total || 0;
    } catch (e) {
        console.error('Summary cards:', e);
    }
}

/* ── Spending by category doughnut ────────────────────────────── */
async function loadCategoryChart(year, month) {
    const wrap = document.getElementById('categoryChartWrap');
    try {
        const res    = await charts.monthly(year, month);
        const t      = chartTheme();
        const data   = res.data.filter(d => Math.abs(d.total) > 0);

        if (categoryChart) { categoryChart.destroy(); categoryChart = null; }

        if (!data.length) {
            wrap.innerHTML = '<div class="text-center text-muted py-5">No spending data for this period.</div>';
            return;
        }

        if (!wrap.querySelector('canvas')) {
            wrap.innerHTML = '<canvas id="categoryChart"></canvas>';
        }

        categoryChart = new Chart(
            document.getElementById('categoryChart').getContext('2d'),
            {
                type: 'doughnut',
                data: {
                    labels:   data.map(d => d.category || `Cat ${d.category_id}`),
                    datasets: [{
                        data:            data.map(d => Math.abs(d.total)),
                        backgroundColor: data.map(d => d.color || '#6c757d'),
                        borderWidth: 2,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onHover: (evt, elements) => {
                        evt.native.target.style.cursor = elements.length ? 'pointer' : 'default';
                    },
                    onClick: (evt, elements) => {
                        if (!elements.length) return;
                        const { year, month } = selectedPeriod();
                        window.location.href = periodUrl(data[elements[0].index].category_id, year, month);
                    },
                    plugins: {
                        legend: { position: 'right', labels: { color: t.text, padding: 12, boxWidth: 14 } },
                        tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${formatAmount(ctx.raw)}` } },
                    },
                },
            }
        );
    } catch (e) {
        wrap.innerHTML = '<div class="text-center text-danger py-5">Failed to load chart.</div>';
        console.error(e);
    }
}

/* ── Budget status bars ───────────────────────────────────────── */
async function loadBudgetStatus(year, month) {
    const el = document.getElementById('budgetStatus');
    try {
        const res = await charts.budgetStatus(year, month);
        if (!res.data.length) {
            el.innerHTML = '<div class="text-muted text-center py-4">No budget data.</div>';
            return;
        }

        el.innerHTML = res.data.map(d => {
            const pct   = Math.min(d.percentage || 0, 100);
            const color = pct >= 100 ? 'danger' : pct >= 80 ? 'warning' : 'success';
            const limitTxt = d.budget > 0
                ? `${formatAmount(d.actual)} / ${formatAmount(d.budget)}`
                : formatAmount(d.actual);

            return `
            <div class="mb-3" style="cursor:pointer" data-cat-id="${d.category_id}">
                <div class="d-flex justify-content-between small mb-1">
                    <span>
                        <span class="cat-dot" style="background:${d.color || '#6c757d'}"></span>
                        ${d.category}
                    </span>
                    <span class="text-muted">${limitTxt}</span>
                </div>
                ${d.budget > 0
                    ? `<div class="progress"><div class="progress-bar bg-${color}" style="width:${pct}%"></div></div>`
                    : '<div class="text-muted small fst-italic">No limit set</div>'
                }
            </div>`;
        }).join('');
    } catch (e) {
        el.innerHTML = '<div class="text-danger text-center py-4">Failed to load.</div>';
    }
}

/* ── 6-month spending trend ───────────────────────────────────── */
async function loadTrendChart(year) {
    try {
        const res = await charts.trend({ year, months: 6 });
        const t   = chartTheme();

        if (trendChart) { trendChart.destroy(); trendChart = null; }

        trendChart = new Chart(
            document.getElementById('trendChart').getContext('2d'),
            {
                type: 'line',
                data: {
                    labels:   res.data.map(d => d.month),
                    datasets: [{
                        label:           'Total Spent',
                        data:            res.data.map(d => Math.abs(d.total)),
                        borderColor:     '#0d6efd',
                        backgroundColor: 'rgba(13,110,253,0.08)',
                        fill:            true,
                        tension:         0.3,
                        pointRadius:     5,
                        pointHoverRadius: 7,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { callbacks: { label: ctx => ` ${formatAmount(ctx.raw)}` } },
                    },
                    scales: {
                        x: { ticks: { color: t.text }, grid: { color: t.grid } },
                        y: {
                            ticks: { color: t.text, callback: v => formatAmount(v) },
                            grid:  { color: t.grid },
                        },
                    },
                },
            }
        );
    } catch (e) {
        console.error('Trend chart:', e);
    }
}

/* ── Top merchants table ──────────────────────────────────────── */
async function loadTopMerchants(year, month) {
    const tbody = document.querySelector('#merchantsTable tbody');
    try {
        const res = await charts.topMerchants({ year, month, limit: 10 });
        if (!res.data.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">No data.</td></tr>';
            return;
        }
        tbody.innerHTML = res.data.map((m, i) => `
            <tr>
                <td class="text-muted">${i + 1}</td>
                <td>${m.merchant}</td>
                <td class="text-end">${m.count}</td>
                <td class="text-end amount-expense">${formatAmount(m.total)}</td>
            </tr>
        `).join('');
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-danger py-4">Failed to load.</td></tr>';
    }
}

/* ── Theme change: redraw charts ──────────────────────────────── */
function onThemeChange() {
    const { year, month } = selectedPeriod();
    loadCategoryChart(year, month);
    loadTrendChart(year);
}

/* ── Bootstrap ────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', async () => {
    await initSelectors();
    loadDashboard();

    document.getElementById('refreshBtn').addEventListener('click', loadDashboard);
    document.getElementById('monthSelect').addEventListener('change', loadDashboard);
    // yearSelect change → loadDashboard is wired inside initSelectors

    document.getElementById('budgetStatus').addEventListener('click', e => {
        const row = e.target.closest('[data-cat-id]');
        if (!row) return;
        const { year, month } = selectedPeriod();
        window.location.href = periodUrl(row.dataset.catId, year, month);
    });
});