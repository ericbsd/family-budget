let allCats        = [];
let currentPage    = 0;
let deleteTargetId = null;
const PAGE_SIZE    = 50;

/* ── Init ─────────────────────────────────────────────────────── */
async function init() {
    allCats = (await categories.list()).data;
    populateCategoryDropdowns();
    readURLFilters();
    await loadTransactions();
    setupListeners();
}

function populateCategoryDropdowns() {
    const opts = allCats.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    document.getElementById('filterCategory').innerHTML =
        '<option value="">All categories</option>' + opts;
    document.getElementById('editCategory').innerHTML = opts;
    document.getElementById('addCategory').innerHTML  = opts;
}

function readURLFilters() {
    const p = new URLSearchParams(window.location.search);
    if (p.get('category_id') !== null) {
        document.getElementById('filterCategory').value = p.get('category_id');
    }
    if (p.get('start_date')) {
        document.getElementById('filterFrom').value = p.get('start_date');
    }
    if (p.get('end_date')) {
        document.getElementById('filterTo').value = p.get('end_date');
    }
}

/* ── Build query params from filter bar ───────────────────────── */
function buildParams() {
    const from  = document.getElementById('filterFrom').value;
    const to    = document.getElementById('filterTo').value;
    const cat   = document.getElementById('filterCategory').value;
    const sort  = document.getElementById('filterSort').value;
    const order = document.getElementById('filterOrder').value;

    const p = { sort, order, limit: PAGE_SIZE, offset: currentPage * PAGE_SIZE };
    if (from) p.start_date  = from;
    if (to)   p.end_date    = to;
    if (cat !== '') p.category_id = cat;
    return p;
}

/* ── Load & render ────────────────────────────────────────────── */
async function loadTransactions() {
    const tbody = document.querySelector('#txTable tbody');
    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4">' +
        '<div class="spinner-border spinner-border-sm text-secondary"></div></td></tr>';

    try {
        const res = await transactions.list(buildParams());
        renderTable(res.data);
        renderPagination(res.total, res.limit, res.offset);
        document.getElementById('txInfo').textContent =
            `Showing ${res.data.length} of ${res.total} transactions`;
    } catch (e) {
        tbody.innerHTML =
            `<tr><td colspan="7" class="text-center text-danger py-4">${e.message}</td></tr>`;
    }
}

function renderTable(txList) {
    const tbody = document.querySelector('#txTable tbody');
    if (!txList.length) {
        tbody.innerHTML =
            '<tr><td colspan="7" class="text-center text-muted py-4">No transactions found.</td></tr>';
        return;
    }

    tbody.innerHTML = txList.map(t => {
        const cat       = getCategoryById(allCats, t.category_id);
        const amtClass  = t.amount < 0 ? 'amount-expense' : 'amount-income';
        const sign      = t.amount < 0 ? '−' : '+';
        const autoBadge = t.auto_categorized
            ? `<span class="badge badge-auto bg-secondary ms-1"
                    title="Auto-categorized – confidence ${Math.round((t.confidence || 0) * 100)}%">A</span>`
            : '';

        return `
        <tr>
            <td><input type="checkbox" class="form-check-input row-check" value="${t._id}"></td>
            <td class="text-nowrap small">${formatDate(t.date)}</td>
            <td class="cell-truncate" style="max-width:220px" title="${t.description}">${t.description}</td>
            <td class="text-end text-nowrap ${amtClass}">${sign}${formatAmount(t.amount)}</td>
            <td>${categoryBadge(cat)}${autoBadge}</td>
            <td class="cell-truncate text-muted small" style="max-width:140px">${t.notes || ''}</td>
            <td class="text-nowrap">
                <button class="btn btn-sm btn-outline-secondary py-0 px-1 edit-btn"
                        data-id="${t._id}" title="Edit">
                    <i class="bi bi-pencil"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger py-0 px-1 ms-1 delete-btn"
                        data-id="${t._id}" title="Delete">
                    <i class="bi bi-trash"></i>
                </button>
            </td>
        </tr>`;
    }).join('');
}

/* ── Pagination ───────────────────────────────────────────────── */
function renderPagination(total, limit, offset) {
    const totalPages = Math.ceil(total / limit);
    const current    = Math.floor(offset / limit);
    const ul         = document.getElementById('pagination');
    if (totalPages <= 1) { ul.innerHTML = ''; return; }

    const prev = `<li class="page-item ${current === 0 ? 'disabled' : ''}">
        <a class="page-link" href="#" data-page="${current - 1}">‹</a></li>`;
    const next = `<li class="page-item ${current >= totalPages - 1 ? 'disabled' : ''}">
        <a class="page-link" href="#" data-page="${current + 1}">›</a></li>`;

    const pages = [];
    for (let i = Math.max(0, current - 2); i <= Math.min(totalPages - 1, current + 2); i++) {
        pages.push(`<li class="page-item ${i === current ? 'active' : ''}">
            <a class="page-link" href="#" data-page="${i}">${i + 1}</a></li>`);
    }

    ul.innerHTML = prev + pages.join('') + next;
}

/* ── Edit modal ───────────────────────────────────────────────── */
async function openEditModal(id) {
    try {
        const res = await transactions.get(id);
        const t   = res.data;
        document.getElementById('editId').value               = t._id;
        document.getElementById('editDate').value             = t.date ? t.date.slice(0, 10) : '';
        document.getElementById('editDescription').value      = t.description;
        document.getElementById('editAmount').value           = t.amount;
        document.getElementById('editCategory').value         = t.category_id;
        document.getElementById('editNotes').value            = t.notes || '';
        document.getElementById('editBatchCategorize').checked = true;
        new bootstrap.Modal(document.getElementById('editModal')).show();
    } catch (e) {
        showToast(e.message, 'danger');
    }
}

async function saveEdit() {
    const id   = document.getElementById('editId').value;
    const data = {
        date:             document.getElementById('editDate').value,
        description:      document.getElementById('editDescription').value,
        amount:           parseFloat(document.getElementById('editAmount').value),
        category_id:      parseInt(document.getElementById('editCategory').value),
        notes:            document.getElementById('editNotes').value,
        batch_categorize: document.getElementById('editBatchCategorize').checked,
    };

    try {
        const res = await transactions.update(id, data);
        bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
        const batched = res.data?.batch_categorized;
        showToast(
            batched > 0
                ? `Saved. ${batched} similar transaction(s) also auto-categorized.`
                : 'Transaction updated.',
            'success'
        );
        await loadTransactions();
    } catch (e) {
        showToast(e.message, 'danger');
    }
}

/* ── Add modal ────────────────────────────────────────────────── */
async function saveAdd() {
    const data = {
        date:        document.getElementById('addDate').value,
        description: document.getElementById('addDescription').value,
        amount:      parseFloat(document.getElementById('addAmount').value),
        category_id: parseInt(document.getElementById('addCategory').value),
        notes:       document.getElementById('addNotes').value,
    };

    try {
        await transactions.create(data);
        bootstrap.Modal.getInstance(document.getElementById('addModal')).hide();
        showToast('Transaction added.', 'success');
        // Reset form
        ['addDate','addDescription','addAmount','addNotes'].forEach(id => {
            document.getElementById(id).value = '';
        });
        document.getElementById('addDate').value = new Date().toISOString().slice(0, 10);
        await loadTransactions();
    } catch (e) {
        showToast(e.message, 'danger');
    }
}

/* ── Delete ───────────────────────────────────────────────────── */
async function confirmDelete() {
    try {
        await transactions.remove(deleteTargetId);
        bootstrap.Modal.getInstance(document.getElementById('deleteModal')).hide();
        showToast('Transaction deleted.', 'success');
        await loadTransactions();
    } catch (e) {
        showToast(e.message, 'danger');
    }
}

/* ── Bulk delete ──────────────────────────────────────────────── */
async function bulkDelete() {
    const ids = [...document.querySelectorAll('.row-check:checked')].map(cb => cb.value);
    if (!ids.length) return;
    if (!confirm(`Delete ${ids.length} transaction(s)? This cannot be undone.`)) return;

    try {
        await transactions.bulkDelete(ids);
        showToast(`${ids.length} transaction(s) deleted.`, 'success');
        document.getElementById('selectAll').checked = false;
        updateBulkBar();
        await loadTransactions();
    } catch (e) {
        showToast(e.message, 'danger');
    }
}

function updateBulkBar() {
    const count = document.querySelectorAll('.row-check:checked').length;
    document.getElementById('selectedCount').textContent = count;
    document.getElementById('bulkDeleteBtn').classList.toggle('d-none', count === 0);
}

/* ── Event listeners ──────────────────────────────────────────── */
function setupListeners() {
    document.getElementById('applyFilters').addEventListener('click', () => {
        currentPage = 0;
        loadTransactions();
    });

    document.getElementById('clearFilters').addEventListener('click', () => {
        ['filterFrom','filterTo'].forEach(id => document.getElementById(id).value = '');
        document.getElementById('filterCategory').value = '';
        document.getElementById('filterSort').value     = 'date';
        document.getElementById('filterOrder').value    = 'desc';
        currentPage = 0;
        loadTransactions();
    });

    // Table delegation
    document.getElementById('txTable').addEventListener('click', e => {
        const edit   = e.target.closest('.edit-btn');
        const del    = e.target.closest('.delete-btn');
        const check  = e.target.closest('.row-check');
        if (edit)  openEditModal(edit.dataset.id);
        if (del)   { deleteTargetId = del.dataset.id; new bootstrap.Modal(document.getElementById('deleteModal')).show(); }
        if (check) updateBulkBar();
    });

    document.getElementById('selectAll').addEventListener('change', e => {
        document.querySelectorAll('.row-check').forEach(cb => cb.checked = e.target.checked);
        updateBulkBar();
    });

    document.getElementById('pagination').addEventListener('click', e => {
        e.preventDefault();
        const a = e.target.closest('a[data-page]');
        if (a) { currentPage = parseInt(a.dataset.page); loadTransactions(); }
    });

    document.getElementById('saveEditBtn').addEventListener('click', saveEdit);
    document.getElementById('saveAddBtn').addEventListener('click', saveAdd);
    document.getElementById('confirmDeleteBtn').addEventListener('click', confirmDelete);
    document.getElementById('bulkDeleteBtn').addEventListener('click', bulkDelete);

    // Pre-fill today's date in add modal
    document.getElementById('addDate').value = new Date().toISOString().slice(0, 10);
}

document.addEventListener('DOMContentLoaded', init);