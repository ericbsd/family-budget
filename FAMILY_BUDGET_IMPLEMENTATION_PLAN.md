# Family Budget — Implementation Plan

## Project Goal
A Flask/Jinja2 family budget tracker with CSV import, smart auto-categorization,
and spending visualization. Server-side rendered — no client-side API calls.

---

## Tech Stack
- **Backend:** Flask 3.1.2, Flask-PyMongo, Flask-CORS
- **Database:** MongoDB (localhost:27017/budget_app)
- **Frontend:** Bootstrap 5.3.2, Bootstrap Icons, Chart.js 4.4.0
- **Rendering:** Jinja2 server-side templates (no JS framework)
- **Testing:** pytest, pytest-flask, Playwright (via pkg on FreeBSD)
- **Python:** 3.11 | **OS:** FreeBSD 14

---

## Project Structure

```
family-budget/
├── app.py                  # Flask factory — registers blueprints, Jinja2 filters
├── web.py                  # Web blueprint — all page routes + POST handlers
├── config.py               # Config classes (dev/test/prod)
│
├── api/                    # REST API blueprints (still usable independently)
│   ├── transactions.py     # /api/transactions CRUD
│   ├── categories.py       # /api/categories CRUD
│   ├── upload.py           # /api/upload/csv
│   └── charts.py           # /api/charts/* aggregations
│
├── models/
│   ├── transaction.py      # Transaction.create(), to_json()
│   └── category.py         # Category.create(), get_next_id()
│
├── utils/
│   ├── db.py               # mongo = PyMongo() singleton
│   ├── db_init.py          # init_db(), reset_db() — seeds categories
│   ├── csv_parser.py       # CSVParser.parse_csv(), validate_csv()
│   ├── categorization.py   # AutoCategorizer — fuzzy matching + learning
│   ├── aggregations.py     # Aggregations — chart/dashboard data pipelines
│   ├── validators.py       # validate_json_request()
│   └── responses.py        # success_response(), error_response()
│
├── templates/
│   ├── base.html           # Layout — navbar, flash messages, dark/light mode
│   ├── dashboard.html      # Charts, budget status, top merchants
│   ├── transactions.html   # Table with filters, pagination, add/edit/delete
│   ├── upload.html         # CSV upload form + history table
│   └── categories.html     # Category cards with add/edit/delete
│
├── static/
│   └── css/
│       └── style.css
│
└── tests/
    ├── conftest.py
    ├── test_api/
    ├── test_ui/
    ├── test_utils/
    └── fixtures/
```

---

## Categories (21 total, ordered by priority of need)

| ID | Name          | Group          | Limit/mo  |
|----|---------------|----------------|-----------|
| 0  | Uncategorized | System         | —         |
| 1  | Entry         | System         | —         |
| 2  | Transaction   | System         | —         |
| 3  | Home          | Housing        | $1,500    |
| 4  | Utilities     | Housing        | $300      |
| 5  | Telecom       | Housing        | $200      |
| 6  | Auto          | Transportation | $400      |
| 7  | Gas           | Transportation | $200      |
| 8  | Groceries     | Food           | $500      |
| 9  | Restaurants   | Food           | $300      |
| 10 | Health        | Health         | $200      |
| 11 | Personal Care | Health         | $100      |
| 12 | Clothing      | Family         | $150      |
| 13 | Education     | Family         | —         |
| 14 | Entertainment | Lifestyle      | $150      |
| 15 | Subscriptions | Lifestyle      | $50       |
| 16 | Savings       | Financial      | —         |
| 17 | Investment    | Financial      | —         |
| 18 | Gift          | Giving         | $100      |
| 19 | Donations     | Giving         | $100      |
| 20 | Fee           | Other          | —         |

**System categories** (0, 1, 2): name/color/description protected; monthly_limit editable.
Entry (1), Transaction (2), Savings (16), and Investment (17) are excluded from the spending
views (category chart, budget status, trend, top merchants) via `EXCLUDED_CATEGORY_IDS`.
Transaction (2), Savings (16), and Investment (17) are excluded from Total Spent and Total Income
on the dashboard via `SUMMARY_EXCLUDED_CATEGORY_IDS`. Entry still counts as income.
Positive-amount transactions are auto-tagged as Entry (ID 1).
Savings account + positive amount → auto-tagged as Savings (ID 16) instead of Entry (ID 1).

## Account Types

| Type            | Page      | Payment treatment                          |
|-----------------|-----------|-------------------------------------------|
| checking        | —         | n/a                                        |
| savings         | Financial | Transfer — excluded from spending          |
| investment      | Financial | Transfer — excluded from spending          |
| credit_card     | Debt      | Transfer — excluded from spending          |
| line_of_credit  | Debt      | Transfer — excluded from spending          |
| loan            | Debt      | Transfer — excluded from spending          |
| mortgage        | Debt      | Spending — counted as expense              |

---

## Completed Phases

### ✅ Phase 1 — Core Setup
- Flask app factory pattern (`app.py`)
- MongoDB connection + indexes
- Config classes (dev/test/prod)

### ✅ Phase 2 — Data Models
- `models/transaction.py` — Transaction.create(), to_json()
- `models/category.py` — Category.create(), get_next_id()
- MongoDB collections: transactions, categories, categorization_rules, uploads

### ✅ Phase 3 — REST API
- `api/transactions.py` — full CRUD + filters
- `api/categories.py` — full CRUD with system protection
- `api/upload.py` — CSV upload + validation
- `api/charts.py` — aggregation endpoints

### ✅ Phase 4 — Utilities
- `utils/csv_parser.py` — multi-format Canadian bank CSV support
- `utils/categorization.py` — AutoCategorizer with fuzzy matching + learning
- `utils/aggregations.py` — dashboard/chart MongoDB pipelines
- `utils/validators.py`, `utils/responses.py`

### ✅ Phase 5 — Web UI (Flask/Jinja2)
Server-side rendering — no client-side API calls, no JS files.

**Dashboard** (`/dashboard`)
- Month/year selector (defaults to last month with data; shows empty state if no transactions)
- Summary cards: total spent, total income, transaction count, uncategorized count, savings (this month + all-time), investment (this month + all-time)
- Savings and Investment excluded from Total Spent and Total Income
- Spending by category doughnut chart (Chart.js, data from Flask)
- Budget status progress bars per category
- Spending trend line chart — last 6 months
- Top merchants table

**Transactions** (`/transactions`)
- Filter bar: date range, category, sort, order (GET form)
- Paginated table (50/page) with category badge + auto-categorized indicator
- Add transaction modal (`<form method="post">`)
- Edit transaction modal (data-* attributes + 10-line inline script)
- Delete with inline form + browser confirm()
- On edit: AutoCategorizer learns + batch-categorizes similar transactions

**Upload** (`/upload`)
- Single file input form → POST → Flask processes + flash result
- Upload history table (Jinja2, server-rendered)
- Auto-categorization runs on every imported row

**Categories** (`/categories`)
- Card grid with color stripe, name badge, description, limit
- Add/edit/delete via Bootstrap modals with `<form method="post">`
- System categories: name/color protected; limit editable
- Non-system: fully editable and deletable (blocked if used by transactions)

### ✅ Phase 6 — Smart Auto-Categorization
- Fuzzy merchant matching (fuzzywuzzy)
- Learns from every manual categorization
- Batch-categorizes similar existing transactions on edit
- Confidence score stored per transaction
- Positive amounts → Entry (ID 1) by default

### ✅ Phase 8 — Multi-Account System
Track which bank account each transaction belongs to.

- `accounts` collection: id, name, type (checking/savings/credit_card/line_of_credit/loan/mortgage/investment), institution, color, currency (CAD/USD)
- Default seed: "Chequing" (ID 1, type: checking)
- `account_id` field on every transaction
- Upload page: account selector required before import
- Transactions page: account filter + account column with badge per row
- Add and edit modals: account selector
- `/accounts` CRUD page (mirrors categories page)
- Savings account + positive amount → Savings category (ID 16) instead of Entry

### ✅ Phase 9 — Transfer Detection
Automatically detect inter-account transfers and tag them as Transaction (ID 2), excluded from spending.

**Auto-detected transfer pairs** (same amount, opposite sign, within 3 days, different accounts):
- Chequing → Savings
- Chequing → Investment
- Chequing → Credit card payment
- Chequing → Line of credit payment
- Chequing → Loan payment

**Not a transfer — counted as spending:**
- Mortgage payments (always counted as a Housing expense)
- Credit card withdrawals (always purchases)

Key facts:
- `line_of_credit` added as a valid account type (`models/account.py`)
- `utils/transfer_detection.py` — `detect_transfers(mongo)`, groups
  transaction candidates by absolute amount, pairs opposite-sign legs across
  different accounts within 3 days, excludes mortgage accounts entirely
  and credit card withdrawals
- Candidates are Uncategorized transactions, or Entry, Savings, or Investment
  transactions with `auto_categorized: True`. Manual edits (web and API) set
  `auto_categorized: False`, so a manually categorized transaction is never overridden
- Both legs must be in the same account currency
- Each tagged leg stores its partner in `transfer_partner_id`. When one leg is
  recategorized or deleted (web, API single and bulk delete),
  `release_transfer_partner()` unlinks the other leg and re-runs
  auto-categorization on it
- Runs automatically at the end of every CSV upload (web `_handle_upload_post`
  and `POST /api/upload/csv`, which now accepts an optional `account_id`) and on
  demand via a "Detect Transfers" button on the Transactions page
  (`POST /transactions/detect-transfers`)
- Tests: `tests/test_utils/test_transfer_detection.py`

---

## Pending Phases

### 🔲 Phase 10 — Financial Page
Combined savings and investment account overview.

- `/financial` page in navbar
- Summary cards: total saved (all-time balance) + this month's contributions, total invested (all-time balance) + this month's contributions
- Table per account showing transaction history

### 🔲 Phase 11 — Debt Page
Credit card, line of credit, loan, and mortgage account overview.

- `/debt` page in navbar
- Outstanding balance per account (running total)
- Table per account showing payment history
- Credit card / line of credit / loan payments auto-detected as transfers (excluded from spending)
- Mortgage payments counted as spending (Housing expense)

### 🔲 Phase 12 — Tests

#### Structure
```
tests/
├── conftest.py              # Flask test app, MongoDB test DB, sample data fixtures
├── fixtures/
│   ├── sample_td.csv        # TD Bank format
│   ├── sample_rbc.csv       # RBC format
│   └── test_data.json       # Sample transactions/categories
├── test_api/
│   ├── test_transactions.py # CRUD, filters, pagination
│   ├── test_categories.py   # CRUD, system protection
│   ├── test_upload.py       # CSV parsing, auto-categorization
│   └── test_charts.py       # Aggregation endpoints
├── test_utils/
│   ├── test_csv_parser.py   # Multi-format parsing, edge cases
│   ├── test_categorization.py
│   └── test_aggregations.py
└── test_ui/                 # Playwright end-to-end
    ├── test_dashboard.py
    ├── test_upload_flow.py
    └── test_transactions.py
```

#### Running tests
```bash
source .venv/bin/activate
pytest                          # all tests
pytest tests/test_api/ -v       # API only
pytest tests/test_ui/ -v        # Playwright UI only
pytest --cov=. --cov-report=html
```

#### Coverage targets
- API endpoints: 90%+
- Utilities (csv_parser, categorization, aggregations): 95%+
- UI critical paths: upload flow, add/edit/delete transaction, category CRUD

---

## Running the App

```bash
service mongod start
source .venv/bin/activate
python app.py          # http://localhost:5000
```

Reset and re-seed DB:
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