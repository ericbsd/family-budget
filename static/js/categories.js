let editingCatId    = null;
let deleteCatTarget = null;

/* ── Random colour generator ──────────────────────────────────── */
function randomColor() {
    // Use a golden-ratio hue step for visually distinct colours,
    // with fixed saturation/lightness so they always look good.
    const hue = Math.floor(Math.random() * 360);
    const h = hue / 360, s = 0.65, l = 0.50;
    // HSL → RGB → hex
    const a = s * Math.min(l, 1 - l);
    const f = n => {
        const k = (n + h * 12) % 12;
        const c = l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
        return Math.round(255 * c).toString(16).padStart(2, '0');
    };
    return `#${f(0)}${f(8)}${f(4)}`;
}

const PALETTE = [
    // Row 1 — Reds & Pinks
    '#e53935','#e91e63','#f06292','#f48fb1','#ff8a65','#ffb300','#fdd835',
    // Row 2 — Purples & Blues
    '#9c27b0','#673ab7','#5e35b1','#3949ab','#1e88e5','#039be5','#29b6f6',
    // Row 3 — Teals & Greens
    '#00acc1','#00897b','#43a047','#7cb342','#8bc34a','#cddc39','#aed581',
    // Row 4 — Neutrals & Others
    '#795548','#6d4c41','#9e9e9e','#607d8b','#546e7a','#4db6ac','#80cbc4',
];

function applyColor(hex) {
    document.getElementById('catColor').value = hex;
    document.getElementById('catColorSwatch').style.background = hex;
    document.getElementById('catColorPicker').value = hex;

    // Highlight the selected swatch in the palette
    document.querySelectorAll('#colorPalette .color-chip').forEach(chip => {
        chip.style.outline = chip.dataset.color === hex ? '3px solid var(--bs-body-color)' : 'none';
        chip.style.outlineOffset = '2px';
    });
}

function buildPalette() {
    const container = document.getElementById('colorPalette');
    container.innerHTML = PALETTE.map(c => `
        <div class="color-chip" data-color="${c}"
             style="width:1.8rem;height:1.8rem;border-radius:.375rem;background:${c};cursor:pointer;
                    border:1px solid rgba(0,0,0,.15)"
             title="${c}"></div>
    `).join('');
    container.querySelectorAll('.color-chip').forEach(chip =>
        chip.addEventListener('click', () => applyColor(chip.dataset.color))
    );
}

/* ── Load & render category cards ─────────────────────────────── */
async function loadCategories() {
    const grid = document.getElementById('categoriesGrid');
    grid.innerHTML = '<div class="col-12 text-center text-muted py-5">' +
        '<div class="spinner-border spinner-border-sm text-secondary me-2"></div>Loading…</div>';

    try {
        const res = await categories.list();
        if (!res.data.length) {
            grid.innerHTML =
                '<div class="col-12 text-center text-muted py-5">No categories found.</div>';
            return;
        }
        grid.innerHTML = res.data.map(renderCard).join('');
        attachCardListeners();
    } catch (e) {
        grid.innerHTML = `<div class="col-12 text-center text-danger py-5">${e.message}</div>`;
    }
}

function renderCard(c) {
    const isSystem = c.is_system === true;
    const limitTxt = c.monthly_limit > 0
        ? `<span class="text-muted small">Limit: ${formatAmount(c.monthly_limit)}/mo</span>`
        : `<span class="text-muted small fst-italic">No limit</span>`;

    const actions = isSystem ? '' : `
        <button class="btn btn-sm btn-outline-secondary py-0 px-1 edit-cat-btn"
                data-id="${c.id}" title="Edit">
            <i class="bi bi-pencil"></i>
        </button>
        <button class="btn btn-sm btn-outline-danger py-0 px-1 ms-1 delete-cat-btn"
                data-id="${c.id}" data-name="${c.name}" title="Delete">
            <i class="bi bi-trash"></i>
        </button>`;

    return `
    <div class="col-sm-6 col-lg-4">
        <div class="card category-card h-100">
            <div class="color-stripe" style="background:${c.color}"></div>
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-start gap-2">
                    <div style="min-width:0">
                        <h6 class="mb-1 text-truncate">${c.name}</h6>
                        <div class="text-muted small text-truncate">${c.description || '—'}</div>
                    </div>
                    <div class="d-flex gap-1 flex-shrink-0">${actions}</div>
                </div>
                <div class="mt-2 d-flex justify-content-between align-items-center">
                    ${limitTxt}
                    <span class="badge" style="background:${c.color}">ID ${c.id}</span>
                </div>
            </div>
        </div>
    </div>`;
}

/* ── Card button listeners ────────────────────────────────────── */
function attachCardListeners() {
    document.querySelectorAll('.edit-cat-btn').forEach(btn =>
        btn.addEventListener('click', () => openEditModal(parseInt(btn.dataset.id)))
    );
    document.querySelectorAll('.delete-cat-btn').forEach(btn =>
        btn.addEventListener('click', () => {
            deleteCatTarget = parseInt(btn.dataset.id);
            document.getElementById('deleteCatName').textContent = btn.dataset.name;
            new bootstrap.Modal(document.getElementById('deleteCatModal')).show();
        })
    );
}

/* ── Add modal ────────────────────────────────────────────────── */
function openAddModal() {
    editingCatId = null;
    document.getElementById('categoryModalTitle').textContent = 'Add Category';
    document.getElementById('catEditId').value      = '';
    document.getElementById('catName').value        = '';
    document.getElementById('catDescription').value = '';
    buildPalette();
    applyColor(randomColor());
    document.getElementById('catLimit').value       = '';
    new bootstrap.Modal(document.getElementById('categoryModal')).show();
}

/* ── Edit modal ───────────────────────────────────────────────── */
async function openEditModal(id) {
    try {
        const res = await categories.get(id);
        const c   = res.data;
        editingCatId = id;
        document.getElementById('categoryModalTitle').textContent = 'Edit Category';
        document.getElementById('catEditId').value      = c.id;
        document.getElementById('catName').value        = c.name;
        document.getElementById('catDescription').value = c.description || '';
        buildPalette();
        applyColor(c.color);
        document.getElementById('catLimit').value       = c.monthly_limit || '';
        new bootstrap.Modal(document.getElementById('categoryModal')).show();
    } catch (e) {
        showToast(e.message, 'danger');
    }
}

/* ── Save (create or update) ──────────────────────────────────── */
async function saveCategory() {
    const name = document.getElementById('catName').value.trim();
    if (!name) {
        showToast('Name is required.', 'warning');
        return;
    }

    const data = {
        name,
        description:   document.getElementById('catDescription').value.trim(),
        color:         document.getElementById('catColor').value,
        monthly_limit: parseFloat(document.getElementById('catLimit').value) || 0,
    };

    try {
        if (editingCatId !== null) {
            await categories.update(editingCatId, data);
            showToast('Category updated.', 'success');
        } else {
            await categories.create(data);
            showToast('Category created.', 'success');
        }
        bootstrap.Modal.getInstance(document.getElementById('categoryModal')).hide();
        _categoryCache = null;   // clear global category cache
        await loadCategories();
    } catch (e) {
        showToast(e.message, 'danger');
    }
}

/* ── Delete ───────────────────────────────────────────────────── */
async function deleteCategory() {
    try {
        await categories.remove(deleteCatTarget);
        bootstrap.Modal.getInstance(document.getElementById('deleteCatModal')).hide();
        showToast('Category deleted.', 'success');
        _categoryCache = null;
        await loadCategories();
    } catch (e) {
        // API returns a human-readable message for CATEGORY_IN_USE
        showToast(e.message, 'danger');
        bootstrap.Modal.getInstance(document.getElementById('deleteCatModal')).hide();
    }
}

/* ── Init ─────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    loadCategories();

    document.getElementById('addCategoryBtn').addEventListener('click', openAddModal);
    document.getElementById('saveCategoryBtn').addEventListener('click', saveCategory);
    document.getElementById('confirmDeleteCatBtn').addEventListener('click', deleteCategory);

    document.getElementById('randomizeColorBtn').addEventListener('click', () => applyColor(randomColor()));
    document.getElementById('catColorPicker').addEventListener('input', e => applyColor(e.target.value));
});