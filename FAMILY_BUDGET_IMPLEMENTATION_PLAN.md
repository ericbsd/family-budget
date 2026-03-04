# Family Budget - Implementation Plan

## Project Goal
Build a Flask REST API for budget tracking with CSV import, transaction categorization, and spending visualization (monthly/quarterly/annual charts).

---

## Phase 1: Core Setup

### 1.1 Project Initialization
- Create project structure (folders: api, models, utils, templates, static, tests)
- Create requirements.txt with:
  - Core: Flask, Flask-PyMongo, Flask-CORS, pandas, python-dateutil, fuzzywuzzy, python-Levenshtein
  - Testing: pytest, pytest-flask, playwright, pytest-playwright, pytest-cov
- Create app.py with Flask app initialization
- Configure MongoDB connection (localhost:27017/budget_app)

### 1.2 Database Initialization
- Create init_db() function to set up default categories on first run
- Default categories: Groceries, Gas, Restaurants, Entertainment, Utilities, Uncategorized
- Each category has: name, color (hex), monthly_limit, is_default flag
- Create MongoDB indexes on transactions (date, category)

---

## Phase 2: Data Models & Collections

### 2.1 MongoDB Collections

#### transactions:
```python
{
    'date': datetime,
    'description': str,
    'amount': float,
    'category': str,  # Auto-categorized or "Uncategorized"
    'source_file': str,
    'upload_date': datetime,
    'notes': str,
    'auto_categorized': bool,  # True if assigned by system
    'confidence': float  # 0.0-1.0 confidence score for auto-categorization
}
```

#### categories:
```python
{
    'name': str,
    'color': str,  # Hex color
    'monthly_limit': float,
    'is_default': bool,
    'created_date': datetime
}
```

#### categorization_rules:
```python
{
    'pattern': str,  # Merchant pattern (e.g., "COSTCO", "SHELL GAS")
    'category': str,
    'match_type': str,  # "exact", "contains", "fuzzy", "regex"
    'created_date': datetime,
    'last_used': datetime,
    'use_count': int  # How many times this rule has been applied
}
```

#### uploads:
```python
{
    'filename': str,
    'upload_date': datetime,
    'row_count': int,
    'month': str,  # "2024-12"
    'status': str,  # "processed" or "error"
    'categorized_count': int,  # How many were auto-categorized
    'uncategorized_count': int  # How many need manual categorization
}
```

---

## Smart Auto-Categorization Feature

### How It Works:

**First Transaction from a Merchant:**
- User uploads CSV with "COSTCO WHOLESALE #123"
- System assigns "Uncategorized" (no history)
- User manually assigns to "Groceries"
- System creates categorization rule: "COSTCO" → "Groceries"

**Future Transactions:**
- Next CSV has "COSTCO WHOLESALE #456"
- System recognizes pattern "COSTCO"
- Auto-assigns to "Groceries"
- Marks as `auto_categorized: true` with confidence score

**Matching Strategies:**
1. **Exact match**: Full description matches previous transaction
2. **Contains match**: Description contains known merchant name (e.g., "COSTCO")
3. **Fuzzy match**: Similar descriptions (e.g., "COSTCO WHSE" ≈ "COSTCO WHOLESALE")
4. **Custom rules**: User-defined patterns (e.g., "AMZN*" → "Shopping")

**Learning System:**
- Every manual categorization creates/updates a rule
- System tracks rule usage and confidence
- More frequently used rules get higher confidence scores
- Users can review and edit auto-categorizations

**Benefits:**
- Saves time on recurring merchants
- Learns your spending patterns
- Gets smarter over time
- Still allows manual override

---

## Phase 3: REST API Endpoints

### 3.1 Transactions API (`api/transactions.py`)
```
GET    /api/transactions              # List all (with optional filters: date range, category)
GET    /api/transactions/<id>         # Get single transaction
POST   /api/transactions              # Create single transaction
PUT    /api/transactions/<id>         # Update transaction
DELETE /api/transactions/<id>         # Delete transaction
```

### 3.2 Categories API (`api/categories.py`)
```
GET    /api/categories                # List all categories
POST   /api/categories                # Create category
PUT    /api/categories/<id>           # Update category (name, color, limit)
DELETE /api/categories/<id>           # Delete category (only if not default)
```

### 3.3 Upload API (`api/upload.py`)
```
POST   /api/upload/csv                # Upload CSV, parse, save transactions
GET    /api/uploads                   # List upload history
```

### 3.4 Charts API (`api/charts.py`)
```
GET    /api/charts/monthly/<year>/<month>       # Monthly spending by category
GET    /api/charts/quarterly/<year>/<quarter>   # Quarterly spending by category
GET    /api/charts/annual/<year>                # Annual spending by category
GET    /api/budget/status/<year>/<month>        # Budget vs actual per category
```

---

## Phase 4: Utilities

### 4.1 CSV Parser (`utils/csv_parser.py`)
- Function: parse_csv(file) → list of transactions
- Detect date format (MM/DD/YYYY, YYYY-MM-DD, etc.)
- Extract: date, description, amount
- Handle multiple CSV formats (flexible column detection)
- Return standardized transaction dictionaries

### 4.2 Auto-Categorization (`utils/categorization.py`)
- Function: auto_categorize(description) → category name
- Look up previous transactions with similar descriptions
- Use fuzzy string matching (e.g., "COSTCO #123" matches "COSTCO WHOLESALE")
- Support merchant name extraction (remove store numbers, locations)
- Return matched category or "Uncategorized" if no match
- Function: create_categorization_rule(pattern, category) → save rule for future use
- Allow user to create custom matching rules (e.g., "AMZN*" → "Shopping")

### 4.3 Aggregation Helpers (`utils/aggregations.py`)
- Function: aggregate_by_category(start_date, end_date) → spending totals per category
- Function: calculate_budget_status(year, month) → budget vs actual comparison
- MongoDB aggregation pipelines for chart data

### 4.4 Validators (`utils/validators.py`)
- Validate transaction data (required fields, data types)
- Validate category data (name uniqueness, color format)
- Validate date ranges

---

## Phase 5: Web Interface (Basic Testing UI)

### 5.1 Templates (simple HTML for testing)
- dashboard.html: Display charts and summary
- upload.html: CSV upload form
- transactions.html: List transactions with edit/delete
- categories.html: Manage categories

### 5.2 Static Assets
- Chart.js library for pie charts
- Bootstrap 5 for basic styling
- JavaScript for API calls and chart rendering

---

## Phase 6: Key Features Implementation

### 6.1 CSV Upload Flow
1. User uploads CSV file
2. Parse CSV → extract transactions
3. **Smart auto-categorization:**
   - Check if description matches existing transaction patterns
   - If merchant/description seen before → assign same category
   - If new merchant → assign "Uncategorized"
   - Use fuzzy matching for similar descriptions (e.g., "COSTCO #123" matches previous "COSTCO WHOLESALE")
4. Save to transactions collection
5. Record upload metadata
6. Return success with transaction count and categorization stats

### 6.2 Transaction Categorization
1. Display transactions (auto-categorized and uncategorized)
2. Show confidence level for auto-categorized transactions
3. Allow bulk or individual category assignment/correction
4. When user assigns category, system learns the pattern for future transactions
5. Update transaction documents in MongoDB
6. Create/update categorization rules automatically

### 6.3 Chart Generation
1. Aggregate spending by category for selected period
2. Return JSON with: category name, amount, color, percentage
3. Frontend renders pie chart with Chart.js
4. Click slice → show transaction list for that category

### 6.4 Budget Tracking
1. Set monthly limit per category
2. Calculate total spent per category for current month
3. Show budget vs actual in chart/table
4. Visual indicator when exceeding limit

---

## Phase 7: Response Format Standards

### Success Response:
```json
{
  "success": true,
  "data": { ... },
  "count": 10,
  "message": "Optional success message"
}
```

### Error Response:
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error"
  }
}
```

---

## Phase 8: Testing Strategy

### 8.1 Testing Stack
- **pytest** - Test framework
- **pytest-flask** - Flask testing helpers
- **playwright** - UI/E2E testing (auto-waits for interactivity)
- **pytest-playwright** - Playwright integration with pytest
- **pytest-cov** - Code coverage reporting

### 8.2 Test Structure
```
tests/
├── __init__.py
├── conftest.py              # Pytest fixtures
├── pytest.ini               # Pytest configuration
│
├── test_api/                # API tests (Flask Test Client - no browser)
│   ├── __init__.py
│   ├── test_transactions.py
│   ├── test_categories.py
│   ├── test_upload.py
│   └── test_charts.py
│
├── test_ui/                 # UI tests (Playwright - with browser)
│   ├── __init__.py
│   ├── test_dashboard.py
│   ├── test_upload_flow.py
│   ├── test_categorization.py
│   └── test_charts_interaction.py
│
├── test_utils/              # Unit tests
│   ├── __init__.py
│   ├── test_csv_parser.py
│   ├── test_aggregations.py
│   └── test_validators.py
│
└── fixtures/
    ├── sample_visa.csv
    ├── sample_mastercard.csv
    └── test_data.json
```

### 8.3 API Testing (Flask Test Client)
- Test all REST endpoints (GET, POST, PUT, DELETE)
- Test request validation
- Test error responses
- Test authentication (future)
- Fast execution (no browser)

### 8.4 UI Testing (Playwright)
- Test CSV upload workflow
- Test transaction categorization UI
- Test chart interactions (click pie slices)
- Test category management (create, edit, delete)
- Test budget limit warnings
- Playwright auto-waits for elements to be interactable

### 8.5 Pytest Configuration (pytest.ini)
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --strict-markers --tb=short
markers =
    api: API endpoint tests
    ui: UI tests with Playwright
    slow: Slow running tests
    integration: Integration tests
```

### 8.6 Test Fixtures (conftest.py)
- Flask app fixture (test mode)
- MongoDB test database fixture (with cleanup)
- Sample data fixtures (categories, transactions)
- Playwright browser fixtures
- Base URL fixture

### 8.7 Running Tests
```bash
# Install Playwright browsers (one-time)
playwright install

# Run all tests
pytest

# Run only API tests
pytest tests/test_api/ -m api

# Run only UI tests
pytest tests/test_ui/ -m ui

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_api/test_transactions.py

# Run in verbose mode
pytest -v

# Run and show output
pytest -s
```

### 8.8 Test Coverage Goals
- API endpoints: 90%+ coverage
- Utilities (CSV parser, validators): 95%+ coverage
- UI critical paths: All major workflows tested

---

## Implementation Order

**Step 1:** Project setup + MongoDB init  
**Step 2:** Create data models and helper functions  
**Step 3:** Build Transactions API (CRUD)  
**Step 4:** Build Categories API (CRUD)  
**Step 5:** Build CSV upload and parser  
**Step 6:** Build Charts API with aggregations  
**Step 7:** Create basic web UI for testing  
**Step 8:** Add budget tracking features  
**Step 9:** Set up pytest and write API tests  
**Step 10:** Write Playwright UI tests

---

## Testing Approach

**API Testing (pytest + Flask Test Client):**
- Test each API endpoint with Flask test client (no browser needed)
- Test request/response validation
- Test error handling
- Test MongoDB operations
- Fast execution

**UI Testing (pytest + Playwright):**
- Test CSV upload workflow with real browser
- Test chart interactions (Playwright auto-waits for elements)
- Test categorization UI
- Test budget limit features
- Playwright automatically waits for elements to be interactable

**Unit Testing (pytest):**
- Test CSV parsing with various formats
- Test data aggregation functions
- Test validators
- Test helper utilities

**Coverage:**
- Use pytest-cov to ensure adequate test coverage
- Aim for 90%+ coverage on API and utilities

---

## Future Enhancements (Post-Phase 1)

- User authentication (Flask-Login)
- PDF parsing for bank statements
- Transaction search and filtering
- Mobile app (Flutter/React Native)
- Desktop app (Electron/Tauri)
- Recurring transaction detection
- Income tracking
- Export reports (PDF/Excel)

---

## Project Structure

```
family-budget/
├── app.py                      # Main Flask app
├── requirements.txt
├── config.py                   # Configuration
│
├── api/                        # REST API routes
│   ├── __init__.py
│   ├── transactions.py         # Transaction endpoints
│   ├── categories.py           # Category endpoints
│   ├── charts.py              # Chart data endpoints
│   └── upload.py              # File upload endpoints
│
├── models/                     # Data models/helpers
│   ├── __init__.py
│   ├── transaction.py
│   └── category.py
│
├── utils/                      # Utilities
│   ├── __init__.py
│   ├── csv_parser.py          # CSV parsing logic
│   ├── categorization.py      # Smart auto-categorization
│   ├── aggregations.py        # MongoDB aggregation pipelines
│   └── validators.py          # Input validation
│
├── templates/                  # Web interface (Phase 1)
│   ├── base.html
│   ├── dashboard.html
│   ├── upload.html
│   ├── transactions.html
│   └── categories.html
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── api-client.js      # Frontend API calls
│       └── charts.js          # Chart rendering
│
└── tests/                      # Test suite
    ├── __init__.py
    ├── conftest.py            # Pytest fixtures
    ├── pytest.ini             # Pytest configuration
    ├── test_api/              # API tests (Flask Test Client)
    │   ├── __init__.py
    │   ├── test_transactions.py
    │   ├── test_categories.py
    │   ├── test_upload.py
    │   └── test_charts.py
    ├── test_ui/               # UI tests (Playwright)
    │   ├── __init__.py
    │   ├── test_dashboard.py
    │   ├── test_upload_flow.py
    │   ├── test_categorization.py
    │   └── test_charts_interaction.py
    ├── test_utils/            # Unit tests
    │   ├── __init__.py
    │   ├── test_csv_parser.py
    │   ├── test_categorization.py
    │   ├── test_aggregations.py
    │   └── test_validators.py
    └── fixtures/
        ├── sample_visa.csv
        ├── sample_mastercard.csv
        └── test_data.json
```

---

**Ready to implement step-by-step!**
