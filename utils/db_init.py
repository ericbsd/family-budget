"""
Database initialization utilities.
Sets up default categories and creates indexes on first run.
"""
from datetime import datetime


def init_db(mongo):
    """
    Initialize the database with default categories and indexes.
    This function is idempotent - safe to run multiple times.

    Args:
        mongo: Flask-PyMongo instance

    Returns:
        dict: Status of initialization with counts
    """
    db = mongo.db

    # Default categories with colors, descriptions, and monthly limits
    default_categories = [
        {
            'id': 0,
            'name': 'Uncategorized',
            'description': 'Transactions not yet categorized',
            'color': '#9E9E9E',  # Gray
            'monthly_limit': 0.0,
            'is_system': True,
            'created_date': datetime.utcnow()
        },
        {
            'id': 1,
            'name': 'Entry',
            'description': 'Money coming in — salary, deposits, refunds. Excluded from budget charts.',
            'color': '#616161',  # Dark gray
            'monthly_limit': 0.0,
            'is_system': True,
            'created_date': datetime.utcnow()
        },
        {
            'id': 2,
            'name': 'Transaction',
            'description': 'Bank transfers, credit card payments, loan payments.',
            'color': '#546E7A',  # Blue-gray
            'monthly_limit': 0.0,
            'is_system': True,
            'created_date': datetime.utcnow()
        },
        {
            'id': 3,
            'name': 'Fee',
            'description': 'Bank fees, service charges, and account fees',
            'color': '#FF7043',  # Deep orange
            'monthly_limit': 0.0,
            'created_date': datetime.utcnow()
        },
        {
            'id': 4,
            'name': 'Groceries',
            'description': 'Food, household items, and grocery shopping',
            'color': '#4CAF50',  # Green
            'monthly_limit': 500.0,
            'created_date': datetime.utcnow()
        },
        {
            'id': 5,
            'name': 'Gas',
            'description': 'Fuel and gas station purchases',
            'color': '#FF9800',  # Orange
            'monthly_limit': 200.0,
            'created_date': datetime.utcnow()
        },
        {
            'id': 6,
            'name': 'Restaurants',
            'description': 'Dining out, takeout, and food delivery',
            'color': '#F44336',  # Red
            'monthly_limit': 300.0,
            'created_date': datetime.utcnow()
        },
        {
            'id': 7,
            'name': 'Entertainment',
            'description': 'Movies, games, hobbies, and leisure activities',
            'color': '#9C27B0',  # Purple
            'monthly_limit': 150.0,
            'created_date': datetime.utcnow()
        },
        {
            'id': 8,
            'name': 'Utilities',
            'description': 'Electric, water, internet, phone bills',
            'color': '#2196F3',  # Blue
            'monthly_limit': 400.0,
            'created_date': datetime.utcnow()
        },
        {
            'id': 9,
            'name': 'Investment',
            'description': 'Savings, stocks, retirement, and investment accounts',
            'color': '#009688',  # Teal
            'monthly_limit': 1000.0,
            'created_date': datetime.utcnow()
        },
    ]

    categories_created = 0
    categories_existing = 0

    # Insert default categories if they don't exist
    for category in default_categories:
        # Check by both id and name for safety
        existing = db.categories.find_one({'$or': [{'id': category['id']}, {'name': category['name']}]})
        if not existing:
            db.categories.insert_one(category)
            categories_created += 1
        else:
            # Backfill is_system flag on existing system categories
            if category.get('is_system') and not existing.get('is_system'):
                db.categories.update_one({'id': category['id']}, {'$set': {'is_system': True}})
            categories_existing += 1

    # Create unique index on category id field
    db.categories.create_index('id', unique=True)

    # Migrate: tag existing positive uncategorized transactions as Entry
    db.transactions.update_many(
        {'amount': {'$gt': 0}, 'category_id': 0},
        {'$set': {'category_id': 1, 'auto_categorized': True, 'confidence': 1.0}}
    )

    # Create indexes for transactions collection
    # Index on date for efficient date range queries
    db.transactions.create_index('date')

    # Index on category_id for filtering by category
    db.transactions.create_index('category_id')

    # Compound index for date + category_id queries
    db.transactions.create_index([('date', 1), ('category_id', 1)])

    # Create indexes for categorization_rules collection
    db.categorization_rules.create_index('pattern')
    db.categorization_rules.create_index('category_id')

    # Create index for uploads collection
    db.uploads.create_index('upload_date')

    return {
        'categories_created': categories_created,
        'categories_existing': categories_existing,
        'total_categories': categories_created + categories_existing,
        'indexes_created': True
    }


def reset_db(mongo):
    """
    Reset the database by dropping all collections.
    WARNING: This will delete all data!

    Args:
        mongo: Flask-PyMongo instance

    Returns:
        dict: Status of reset operation
    """
    db = mongo.db

    # Drop all collections
    db.transactions.drop()
    db.categories.drop()
    db.categorization_rules.drop()
    db.uploads.drop()

    return {
        'status': 'Database reset complete',
        'collections_dropped': ['transactions', 'categories', 'categorization_rules', 'uploads']
    }
