# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Running the App

```bash
service mongod start                 # FreeBSD — start MongoDB
source .venv/bin/activate
python app.py                        # http://localhost:5000
```

Reset and re-seed the database (wipes all data):
```bash
python -c "
from app import create_app
from utils.db import mongo
from utils.db_init import reset_db, init_db
app = create_app()
with app.app_context():
    reset_db(mongo)
    init_db(mongo)
"
```

Or hit `GET /api/init-db` in a running app to re-seed without dropping data.

## Tests

MongoDB must be running. Playwright is installed via FreeBSD pkg, not pip.

```bash
pytest                          # all tests
pytest -m unit                  # no DB required
pytest -m api                   # Flask test client only
pytest -m ui                    # Playwright browser tests
pytest tests/test_api/test_transactions.py          # single file
pytest tests/test_api/test_transactions.py::test_fn # single test
pytest --cov=. --cov-report=html                    # with coverage
```

## Linting

Always run pylint after every change and fix all warnings before considering work done:

```bash
pylint .
deadcode .                       # dead code detection
```

Never modify `.pylintrc` without asking the user first. Fix warnings in code, not by suppression.

---

## Python Code Style (mandatory — PEP 8 strict)

### Type hints required on all functions

```python
# Yes
def get_next_id(mongo: PyMongo) -> int:

def create(account_id: int, name: str, type_: str) -> dict:
```

### Multi-line function calls — one argument per line

```python
# No
return render_template('dashboard.html',
        year=year, month=month, stats=stats)

# Yes
return render_template(
    'dashboard.html',
    year=year,
    month=month,
    stats=stats,
)
```

### Multi-item lists — one item per line

```python
# No
COLUMNS = ['amount', 'debit', 'credit', 'value']

# Yes
COLUMNS = [
    'amount',
    'debit',
    'credit',
    'value',
]
```

### No aligned spacing on assignments

```python
# No
categorizer   = AutoCategorizer(mongo)
categorized   = 0
uncategorized = 0

# Yes
categorizer = AutoCategorizer(mongo)
categorized = 0
uncategorized = 0
```

### Docstrings — never single-line for non-trivial functions

```python
# No
"""Delete a category if it is not a system category and has no transactions."""

# Yes
"""
Delete a category.

Blocked if the category is a system category or has associated transactions.

Args:
    cat_id: int - Category ID to delete

Returns:
    redirect to /categories
"""
```

### Docstrings — use proper grammar with articles

Use "a", "an", "the" where appropriate. Write full sentences.

```python
# No
"""Parse date string to datetime object."""
"""List all accounts ordered by id."""

# Yes
"""Parse a date string to a datetime object."""
"""List all accounts ordered by their ID."""
```

### Docstrings — no " - " or " — " separators

Use proper sentence structure instead.

```python
# No
"""
Args:
    account_id: Account ID - used to look up the account
"""

# Yes
"""
Args:
    account_id: The account ID used to look up the account.
"""
```

### Variable names — full words, underscores for multiple words

No abbreviations, no type suffixes, no single-letter loop variables.

```python
# No
accts = mongo.db.accounts.find()
txns = mongo.db.transactions.find()
cats = mongo.db.categories.find()
cat_map = {c['id']: c for c in cats}
start_date_str = request.args.get('start_date')
for t in txns: ...

# Yes
accounts = mongo.db.accounts.find()
transactions = mongo.db.transactions.find()
categories = mongo.db.categories.find()
category_map = {category['id']: category for category in categories}
start_date = request.args.get('start_date')
for transaction in transactions: ...
```

### Long return/call statements — break after opening paren

```python
# No
return None, error_response('MISSING_FIELDS',
                             f'Missing required fields: {", ".join(missing)}')

# Yes
return None, error_response(
    'MISSING_FIELDS',
    f'Missing required fields: {", ".join(missing)}'
)
```

---

## Architecture

This is a **Flask/Jinja2 server-side rendered** app. There are no client-side API calls from the web UI — all pages are rendered by Flask routes in `web.py` using data fetched directly from MongoDB.

### Two-layer design

| Layer | Files | Purpose |
|-------|-------|---------|
| **Web UI** | `web.py` + `templates/` | Jinja2 pages, GET/POST form handlers, flash messages |
| **REST API** | `api/*.py` | JSON endpoints (independently usable, not called by the web UI) |

**`web.py`** is the primary file for all UI work. It fetches MongoDB data directly and passes it to Jinja2 templates. POST routes handle all CRUD and redirect back with flash messages.

**`app.py`** is a factory (`create_app()`). It registers all blueprints, defines the `money` and `dateformat` Jinja2 filters, and calls `init_db()` on startup.

### Key conventions

- **No JS files** — `static/js/` is empty. Chart.js (CDN) is the only JS dependency and receives data via `{{ json_var | safe }}` from Flask.
- **Edit modals** use `data-*` attributes on the edit button + a small inline `<script>` (10–15 lines max) to populate a single shared modal. No separate JS file.
- **Delete** uses an inline `<form method="post">` with `onsubmit="return confirm(...)"`.
- **Filters** (transactions page) use `<form method="get">` — page reloads on submit.
- **Flash messages** use Bootstrap alert dismissibles rendered in `base.html`.

### Categorization system (`utils/categorization.py`)

`AutoCategorizer.categorize(description, amount, account_type=None)` returns `{category_id, confidence, match_type}`.

Match priority:
1. Exact match against `categorization_rules` collection
2. Contains match (merchant keyword)
3. Fuzzy match (fuzzywuzzy, threshold 80)
4. Amount-based fallback: positive → Entry (ID 1), unless `account_type == 'savings'` → Savings (ID 16)
5. No match → Uncategorized (ID 0)

`learn_from_categorization(description, category_id)` + `batch_categorize_similar(description, category_id)` are called after every manual edit.

### Category IDs (do not renumber — transactions reference these)

System (protected): 0 Uncategorized, 1 Entry, 2 Transaction
Housing: 3 Home, 4 Utilities, 5 Telecom
Transport: 6 Auto, 7 Gas
Food: 8 Groceries, 9 Restaurants
Health: 10 Health, 11 Personal Care
Family: 12 Clothing, 13 Education
Lifestyle: 14 Entertainment, 15 Subscriptions
Financial: 16 Savings, 17 Investment
Giving: 18 Gift, 19 Donations
Other: 20 Fee

Entry (1), Transaction (2), Savings (16) and Investment (17) are excluded from spending charts via `EXCLUDED_CATEGORY_IDS` in `utils/aggregations.py`. Transaction, Savings and Investment are also excluded from the dashboard income and expense totals via `SUMMARY_EXCLUDED_CATEGORY_IDS`. System categories (0, 1, 2) cannot be deleted or renamed; their `monthly_limit` is editable.

### Dashboard data flow

`web.py::dashboard()` → `utils/aggregations.py` (MongoDB pipelines) → `dashboard.html`.
Chart data is passed as `category_json` and `trend_json` (JSON strings) and consumed by inline Chart.js scripts in `{% block scripts %}`.

### Database

- **MongoDB** at `mongodb://localhost:27017/budget_app` (test: `budget_app_test`)
- Collections: `transactions`, `categories`, `categorization_rules`, `uploads`, `accounts`
- `utils/db.py` exports a `mongo = PyMongo()` singleton imported everywhere
- `utils/db_init.py` seeds categories and accounts; is idempotent (safe to run repeatedly)

### FreeBSD notes

- Playwright is installed from pkg (`/usr/local/share/chromium/chrome`), not pip
- `sysctl kern.ipc.shm_allow_removed=1` must be set for Chromium to work