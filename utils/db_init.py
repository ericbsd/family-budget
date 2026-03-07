"""
Database initialization utilities.
Sets up default categories and creates indexes on the first run.
"""
from datetime import datetime, UTC


def init_db(mongo) -> dict:
    """
    Initialize the database with default categories and indexes.
    This function is idempotent - safe to run multiple times.

    Args:
        mongo: Flask-PyMongo instance

    Returns:
        dict: Status of initialization with counts
    """
    db = mongo.db

    # Default categories ordered by priority of need (Maslow for money)
    default_categories = [
        # ── System (administrative) ────────────────────────────────
        {
            'id': 0,
            'name': 'Uncategorized',
            'description': 'Transactions not yet categorized',
            'color': '#9E9E9E',
            'monthly_limit': 0.0,
            'is_system': True,
            'created_date': datetime.now(UTC)
        },
        {
            'id': 1,
            'name': 'Entry',
            'description': 'Money coming in — salary, deposits, refunds. Excluded from budget charts.',
            'color': '#616161',
            'monthly_limit': 0.0,
            'is_system': True,
            'created_date': datetime.now(UTC)
        },
        {
            'id': 2,
            'name': 'Transaction',
            'description': 'Bank transfers, credit card payments, loan payments.',
            'color': '#546E7A',
            'monthly_limit': 0.0,
            'is_system': True,
            'created_date': datetime.now(UTC)
        },
        # ── Housing ────────────────────────────────────────────────
        {
            'id': 3,
            'name': 'Home',
            'description': 'Mortgage/rent, property tax, home insurance, and maintenance',
            'color': '#795548',
            'monthly_limit': 1500.0,
            'created_date': datetime.now(UTC)
        },
        {
            'id': 4,
            'name': 'Utilities',
            'description': 'Electric, water, and heating/natural gas bills',
            'color': '#1E88E5',
            'monthly_limit': 300.0,
            'created_date': datetime.now(UTC)
        },
        {
            'id': 5,
            'name': 'Telecom',
            'description': 'Internet, cable, cell phones, and home phone',
            'color': '#00ACC1',
            'monthly_limit': 200.0,
            'created_date': datetime.now(UTC)
        },
        # ── Transportation ─────────────────────────────────────────
        {
            'id': 6,
            'name': 'Auto',
            'description': 'Car payments, auto insurance, and vehicle maintenance',
            'color': '#607D8B',
            'monthly_limit': 400.0,
            'created_date': datetime.now(UTC)
        },
        {
            'id': 7,
            'name': 'Gas',
            'description': 'Fuel and gas station purchases',
            'color': '#FF9800',
            'monthly_limit': 200.0,
            'created_date': datetime.now(UTC)
        },
        # ── Food ───────────────────────────────────────────────────
        {
            'id': 8,
            'name': 'Groceries',
            'description': 'Food, household items, and grocery shopping',
            'color': '#4CAF50',
            'monthly_limit': 500.0,
            'created_date': datetime.now(UTC)
        },
        {
            'id': 9,
            'name': 'Restaurants',
            'description': 'Dining out, takeout, and food delivery',
            'color': '#EF5350',
            'monthly_limit': 300.0,
            'created_date': datetime.now(UTC)
        },
        # ── Health & Personal ──────────────────────────────────────
        {
            'id': 10,
            'name': 'Health',
            'description': 'Doctor visits, pharmacy, dental, and health/dental insurance premiums',
            'color': '#66BB6A',
            'monthly_limit': 200.0,
            'created_date': datetime.now(UTC)
        },
        {
            'id': 11,
            'name': 'Personal Care',
            'description': 'Haircuts, salon, spa, and personal hygiene products',
            'color': '#F06292',
            'monthly_limit': 100.0,
            'created_date': datetime.now(UTC)
        },
        # ── Family ─────────────────────────────────────────────────
        {
            'id': 12,
            'name': 'Clothing',
            'description': 'Clothes and shoes for the whole family',
            'color': '#EC407A',
            'monthly_limit': 150.0,
            'created_date': datetime.now(UTC)
        },
        {
            'id': 13,
            'name': 'Education',
            'description': 'Day care, school fees, tutoring, school supplies, and extracurriculars',
            'color': '#FFA726',
            'monthly_limit': 0.0,
            'created_date': datetime.now(UTC)
        },
        # ── Lifestyle ──────────────────────────────────────────────
        {
            'id': 14,
            'name': 'Entertainment',
            'description': 'Movies, games, hobbies, and leisure activities',
            'color': '#AB47BC',
            'monthly_limit': 150.0,
            'created_date': datetime.now(UTC)
        },
        {
            'id': 15,
            'name': 'Subscriptions',
            'description': 'Streaming services, software, and recurring digital subscriptions',
            'color': '#7E57C2',
            'monthly_limit': 50.0,
            'created_date': datetime.now(UTC)
        },
        # ── Financial ──────────────────────────────────────────────
        {
            'id': 16,
            'name': 'Savings',
            'description': 'Money set aside in savings accounts',
            'color': '#26A69A',
            'monthly_limit': 0.0,
            'created_date': datetime.now(UTC)
        },
        {
            'id': 17,
            'name': 'Investment',
            'description': 'Stocks, retirement, and investment accounts',
            'color': '#009688',
            'monthly_limit': 1000.0,
            'created_date': datetime.now(UTC)
        },
        # ── Giving ─────────────────────────────────────────────────
        {
            'id': 18,
            'name': 'Gift',
            'description': 'Birthday, holiday, and special occasion gifts',
            'color': '#FF7043',
            'monthly_limit': 100.0,
            'created_date': datetime.now(UTC)
        },
        {
            'id': 19,
            'name': 'Donations',
            'description': 'Charitable giving and religious contributions',
            'color': '#5C6BC0',
            'monthly_limit': 100.0,
            'created_date': datetime.now(UTC)
        },
        # ── Other ──────────────────────────────────────────────────
        {
            'id': 20,
            'name': 'Fee',
            'description': 'Bank fees, service charges, and account fees',
            'color': '#78909C',
            'monthly_limit': 0.0,
            'created_date': datetime.now(UTC)
        },
    ]

    categories_created = 0
    categories_existing = 0

    # Insert default categories if they don't exist
    for category in default_categories:
        if existing := db.categories.find_one(
            {'$or': [{'id': category['id']}, {'name': category['name']}]}
        ):
            # Backfill is_system flag on existing system categories
            if category.get('is_system') and not existing.get('is_system'):
                db.categories.update_one({'id': category['id']}, {'$set': {'is_system': True}})
            categories_existing += 1
        else:
            db.categories.insert_one(category)
            categories_created += 1
    # Create a unique index on category id field
    db.categories.create_index('id', unique=True)

    # Seed default account
    if not db.accounts.find_one({'id': 1}):
        db.accounts.insert_one({
            'id': 1,
            'name': 'Chequing',
            'type': 'checking',
            'institution': '',
            'color': '#42A5F5',
            'currency': 'CAD',
            'is_active': True,
            'created_date': datetime.now(UTC),
        })
    db.accounts.create_index('id', unique=True)

    # Migrate: tag existing positive uncategorized transactions as Entry
    db.transactions.update_many(
        {'amount': {'$gt': 0}, 'category_id': 0},
        {'$set': {'category_id': 1, 'auto_categorized': True, 'confidence': 1.0}}
    )

    # Create indexes for the transaction collection
    db.transactions.create_index('date')
    db.transactions.create_index('category_id')
    db.transactions.create_index([('date', 1), ('category_id', 1)])

    # Create indexes for the categorization_rules collection
    db.categorization_rules.create_index('pattern')
    db.categorization_rules.create_index('category_id')

    # Create an index for uploads collection
    db.uploads.create_index('upload_date')

    return {
        'categories_created': categories_created,
        'categories_existing': categories_existing,
        'total_categories': categories_created + categories_existing,
        'indexes_created': True
    }


def reset_db(mongo) -> dict:
    """
    Reset the database by dropping all collections.
    WARNING: This will delete all data!

    Args:
        mongo: Flask-PyMongo instance

    Returns:
        dict: Status of reset operation
    """
    db = mongo.db

    db.transactions.drop()
    db.categories.drop()
    db.categorization_rules.drop()
    db.uploads.drop()
    db.accounts.drop()

    return {
        'status': 'Database reset complete',
        'collections_dropped': [
            'transactions',
            'categories',
            'categorization_rules',
            'uploads',
            'accounts',
        ],
    }
