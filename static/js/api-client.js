/* ── API base URL ─────────────────────────────────────────────── */
const API_BASE = '/api';

/* ── Core fetch wrapper ───────────────────────────────────────── */
async function apiRequest(method, endpoint, data = null, isFormData = false) {
    const url = `${API_BASE}${endpoint}`;
    const options = { method };

    if (data !== null) {
        if (isFormData) {
            options.body = data;
        } else {
            options.headers = { 'Content-Type': 'application/json' };
            options.body = JSON.stringify(data);
        }
    }

    const response = await fetch(url, options);
    const json = await response.json();

    if (!json.success) {
        throw new Error(json.error?.message || 'An unexpected error occurred.');
    }
    return json;
}

/* ── Shorthand helpers ────────────────────────────────────────── */
function apiGet(endpoint, params = {}) {
    const qs = new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined))
    ).toString();
    return apiRequest('GET', qs ? `${endpoint}?${qs}` : endpoint);
}
const apiPost   = (ep, data) => apiRequest('POST',   ep, data);
const apiPut    = (ep, data) => apiRequest('PUT',    ep, data);
const apiDelete = (ep, data) => apiRequest('DELETE', ep, data);
const apiUpload = (ep, fd)   => apiRequest('POST',   ep, fd, true);

/* ── Domain-level API objects ─────────────────────────────────── */
const transactions = {
    list:       (params) => apiGet('/transactions', params),
    get:        (id)     => apiGet(`/transactions/${id}`),
    create:     (data)   => apiPost('/transactions', data),
    update:     (id, d)  => apiPut(`/transactions/${id}`, d),
    remove:     (id)     => apiDelete(`/transactions/${id}`),
    bulkDelete: (ids)    => apiDelete('/transactions/bulk', { ids }),
};

const categories = {
    list:   ()       => apiGet('/categories'),
    get:    (id)     => apiGet(`/categories/${id}`),
    create: (data)   => apiPost('/categories', data),
    update: (id, d)  => apiPut(`/categories/${id}`, d),
    remove: (id)     => apiDelete(`/categories/${id}`),
};

const charts = {
    monthly:      (y, m)     => apiGet(`/charts/monthly/${y}/${m}`),
    quarterly:    (y, q)     => apiGet(`/charts/quarterly/${y}/${q}`),
    annual:       (y)        => apiGet(`/charts/annual/${y}`),
    periods:      ()         => apiGet('/charts/periods'),
    budgetStatus: (y, m)     => apiGet(`/budget/status/${y}/${m}`),
    trend:        (params)   => apiGet('/charts/trend', params),
    topMerchants: (params)   => apiGet('/charts/top-merchants', params),
};

const uploads = {
    csv:     (file)   => { const fd = new FormData(); fd.append('file', file); return apiUpload('/upload/csv', fd); },
    validate:(file)   => { const fd = new FormData(); fd.append('file', file); return apiUpload('/upload/validate', fd); },
    history: (params) => apiGet('/uploads', params),
    get:     (id)     => apiGet(`/uploads/${id}`),
};

/* ── UI helpers ───────────────────────────────────────────────── */
function showToast(message, type = 'success') {
    const el   = document.getElementById('toast');
    const body = document.getElementById('toastBody');
    el.className = `toast align-items-center border-0 text-bg-${type}`;
    body.textContent = message;
    bootstrap.Toast.getOrCreateInstance(el, { delay: 4000 }).show();
}

function formatAmount(amount) {
    return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(Math.abs(amount));
}

function formatDate(dateStr) {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('en-CA');
}

/* ── Category cache & helpers ─────────────────────────────────── */
let _categoryCache = null;

async function getCategories() {
    if (!_categoryCache) {
        const res = await categories.list();
        _categoryCache = res.data;
    }
    return _categoryCache;
}

function getCategoryById(cats, id) {
    return cats.find(c => c.id === id) || { name: 'Uncategorized', color: '#6c757d' };
}

function categoryBadge(cat) {
    return `<span class="badge" style="background-color:${cat.color}">${cat.name}</span>`;
}