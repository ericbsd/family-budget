let selectedFile = null;

/* ── File size helper ─────────────────────────────────────────── */
function fmtSize(bytes) {
    if (bytes < 1024)    return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
}

/* ── Show / hide file info section ───────────────────────────── */
function setFile(file) {
    selectedFile = file;
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = fmtSize(file.size);
    document.getElementById('fileInfo').classList.remove('d-none');
    document.getElementById('validateResult').classList.add('d-none');
    document.getElementById('uploadResult').classList.add('d-none');
}

function clearFile() {
    selectedFile = null;
    document.getElementById('fileInput').value = '';
    document.getElementById('fileInfo').classList.add('d-none');
    document.getElementById('validateResult').classList.add('d-none');
    document.getElementById('uploadResult').classList.add('d-none');
}

/* ── Validate CSV ─────────────────────────────────────────────── */
async function validateCSV() {
    if (!selectedFile) return;
    const btn = document.getElementById('validateBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Validating…';

    const el = document.getElementById('validateResult');
    el.classList.remove('d-none');

    try {
        const res     = await uploads.validate(selectedFile);
        const mapping = res.data.column_mapping || {};
        const rows    = Object.entries(mapping)
            .map(([k, v]) => `<li><strong>${k}</strong> → <code>${v}</code></li>`)
            .join('');

        el.innerHTML = `
        <div class="alert alert-success mb-0">
            <div class="fw-medium mb-1"><i class="bi bi-check-circle me-1"></i>CSV looks good!</div>
            <div class="small">
                <strong>Detected column mapping:</strong>
                <ul class="mb-0 mt-1">${rows || '<li>Standard format detected</li>'}</ul>
            </div>
        </div>`;
    } catch (e) {
        el.innerHTML = `
        <div class="alert alert-danger mb-0">
            <i class="bi bi-exclamation-triangle me-1"></i>
            <strong>Validation failed:</strong> ${e.message}
        </div>`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-check2-circle me-1"></i>Validate';
    }
}

/* ── Upload / import CSV ──────────────────────────────────────── */
async function uploadCSV() {
    if (!selectedFile) return;
    const btn = document.getElementById('uploadBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Importing…';

    const el = document.getElementById('uploadResult');
    el.classList.remove('d-none');

    try {
        const res = await uploads.csv(selectedFile);
        const d   = res.data;

        const errorsHTML = d.errors?.length
            ? `<div class="mt-2 small">
                <strong>${d.errors.length} row error(s):</strong>
                <ul class="mb-0 mt-1">
                    ${d.errors.slice(0, 5).map(e => `<li>${e}</li>`).join('')}
                    ${d.errors.length > 5 ? `<li class="text-muted">…and ${d.errors.length - 5} more</li>` : ''}
                </ul>
               </div>`
            : '';

        el.innerHTML = `
        <div class="alert alert-success mb-0">
            <div class="fw-medium mb-2"><i class="bi bi-check-circle me-1"></i>Import complete!</div>
            <div class="row g-2 text-center">
                <div class="col-4">
                    <div class="fs-5 fw-bold">${d.total_rows}</div>
                    <div class="small text-muted">Imported</div>
                </div>
                <div class="col-4">
                    <div class="fs-5 fw-bold text-success">${d.categorized}</div>
                    <div class="small text-muted">Auto-categorized</div>
                </div>
                <div class="col-4">
                    <div class="fs-5 fw-bold text-warning">${d.uncategorized}</div>
                    <div class="small text-muted">Uncategorized</div>
                </div>
            </div>
            ${errorsHTML}
            <div class="mt-3">
                <a href="/transactions" class="btn btn-sm btn-outline-success">
                    View Transactions →
                </a>
            </div>
        </div>`;

        clearFile();
        loadHistory();
    } catch (e) {
        el.innerHTML = `
        <div class="alert alert-danger mb-0">
            <i class="bi bi-exclamation-triangle me-1"></i>
            <strong>Import failed:</strong> ${e.message}
        </div>`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-upload me-1"></i>Import';
    }
}

/* ── Upload history ───────────────────────────────────────────── */
async function loadHistory() {
    const tbody = document.getElementById('historyBody');
    try {
        const res = await uploads.history({ limit: 30 });
        if (!res.data.length) {
            tbody.innerHTML =
                '<tr><td colspan="5" class="text-center text-muted py-4">No uploads yet.</td></tr>';
            return;
        }
        tbody.innerHTML = res.data.map(u => {
            const badge = u.status === 'processed'
                ? '<span class="badge bg-success">Processed</span>'
                : '<span class="badge bg-danger">Error</span>';
            return `
            <tr>
                <td class="cell-truncate" style="max-width:160px" title="${u.filename}">${u.filename}</td>
                <td class="small text-nowrap">${formatDate(u.upload_date)}</td>
                <td class="text-end">${u.row_count}</td>
                <td class="text-end">${u.categorized_count || 0}</td>
                <td>${badge}</td>
            </tr>`;
        }).join('');
    } catch (e) {
        tbody.innerHTML =
            '<tr><td colspan="5" class="text-center text-danger py-4">Failed to load.</td></tr>';
    }
}

/* ── Drop zone wiring ─────────────────────────────────────────── */
function setupDropZone() {
    const zone  = document.getElementById('dropZone');
    const input = document.getElementById('fileInput');

    zone.addEventListener('click', e => {
        if (!e.target.closest('button')) input.click();
    });

    zone.addEventListener('dragover', e => {
        e.preventDefault();
        zone.classList.add('dragover');
    });

    ['dragleave', 'dragend'].forEach(ev =>
        zone.addEventListener(ev, () => zone.classList.remove('dragover'))
    );

    zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) setFile(file);
    });

    input.addEventListener('change', () => {
        if (input.files[0]) setFile(input.files[0]);
    });

    document.getElementById('clearFileBtn').addEventListener('click', clearFile);
    document.getElementById('validateBtn').addEventListener('click', validateCSV);
    document.getElementById('uploadBtn').addEventListener('click', uploadCSV);
    document.getElementById('refreshHistoryBtn').addEventListener('click', loadHistory);
}

document.addEventListener('DOMContentLoaded', () => {
    setupDropZone();
    loadHistory();
});