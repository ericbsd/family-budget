# Family Budget

A self-hosted family budget tracker with CSV import, smart auto-categorization, and spending visualization.

**Stack:** Flask · MongoDB · Bootstrap 5.3 · Chart.js · Vanilla JS

> **Note:** Intended for use on your local network only. Do not expose to the internet.

---

## Features

- Import bank CSV files (auto-detects TD, Desjardins, and other Canadian bank formats)
- Smart auto-categorization that learns from your corrections
- Spending charts by category, trend over time, and top merchants
- Budget limits per category with progress bars
- Dark / light mode

---

## Prerequisites

- Python 3.11+
- MongoDB 6+
- pip / virtualenv

---

## Installation

**1. Clone the repository**
```bash
git clone <repo-url>
cd family-budget
```

**2. Create and activate a virtual environment**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Start MongoDB**

On FreeBSD:
```bash
service mongod start
```

On Linux (systemd):
```bash
sudo systemctl start mongod
```

On macOS (Homebrew):
```bash
brew services start mongodb-community
```

**5. (Optional) Configure environment**

Set environment variables or create a `.env` file in the project root:

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | `development` | `development` / `testing` |
| `MONGO_URI` | `mongodb://localhost:27017/budget_app` | MongoDB connection string |

**6. Run the application**
```bash
python app.py
```

The app will be available at **http://localhost:5000**.

The database is initialized automatically on first run — default categories are seeded and indexes are created.

---

## First Use

1. Go to **Upload** and import a bank CSV file
2. The app will auto-categorize transactions based on merchant names
3. Open **Transactions**, filter by *Uncategorized*, and manually assign categories to anything missed
4. Each manual categorization teaches the system — future uploads will be categorized automatically
5. Set monthly budget limits under **Categories**
6. View spending breakdowns on the **Dashboard**

---

## Default Categories

The app seeds 20 default categories grouped by type:

| Group | Categories |
|-------|-----------|
| System | Uncategorized, Entry, Transaction |
| Housing | Home |
| Food | Groceries, Restaurants |
| Transportation | Auto, Gas |
| Bills | Utilities, Telecom, Subscriptions |
| Health & Personal | Health, Personal Care |
| Lifestyle | Clothing, Entertainment |
| Giving | Gift, Donations |
| Savings | Investment |
| Other | Education, Fee |

All categories are editable. System categories (Uncategorized, Entry, Transaction) cannot be deleted.

---

## Running Tests

Requires MongoDB to be running.

```bash
pytest                        # All tests
pytest -m unit                # Unit tests only (no DB required)
pytest -m api                 # API tests only
```