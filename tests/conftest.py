"""
Pytest configuration and fixtures for Family Budget tests.
"""
import os
import pytest

from app import create_app
from utils.db import mongo
from utils.db_init import init_db


@pytest.fixture(scope='session')
def _app():
    """
    Create Flask application for testing.
    Uses a separate test database to avoid polluting production data.
    """
    # Set test environment
    os.environ['FLASK_ENV'] = 'testing'

    # Create app with test configuration
    test_app = create_app('testing')

    # Override database name for testing
    test_app.config['MONGO_URI'] = 'mongodb://localhost:27017/budget_app_test'

    yield test_app

    # Cleanup: Drop test database after all tests
    with test_app.app_context():
        mongo.cx.drop_database('budget_app_test')


@pytest.fixture(scope='function')
def client(_app):
    """
    Flask test client for making API requests.
    Function-scoped: fresh database for each test.
    """
    with _app.app_context():
        # Clean database before each test
        mongo.cx.drop_database('budget_app_test')

        # Re-initialize database with default categories
        init_db(mongo)

        # Return test client
        yield _app.test_client()


@pytest.fixture(scope='function')
def db(_app):
    """
    Direct database access for test assertions.
    """
    with _app.app_context():
        yield mongo.db


@pytest.fixture
def sample_transaction():
    """
    Sample transaction data for testing.
    """
    return {
        'date': '2025-11-15',
        'description': 'COSTCO WHOLESALE #123',
        'amount': -145.67,
        'category_id': 0,
        'notes': 'Grocery shopping'
    }


@pytest.fixture
def sample_category():
    """
    Sample category data for testing.
    """
    return {
        'name': 'Test Category',
        'description': 'Category for testing',
        'color': '#FF5733',
        'monthly_limit': 500.00
    }


@pytest.fixture
def bank_csv_content():
    """
    Real Canadian bank CSV format for testing.
    """
    return """Account Type,Account Number,Transaction Date,Cheque Number,Description 1,Description 2,CAD$,USD$
Visa,4510154206791790,11/1/2025,,NETFLIX.COM Vancouver,,-27.59,
Visa,4510154206791790,11/2/2025,,STEAM PURCHASE SEATTLE,,-20.69,
Visa,4510154206791790,11/2/2025,,PrimeVideo.c*NK4SX54K2 www.amazon.ca,,-5.74,
Visa,4510154206791790,11/3/2025,,Amazon.ca*NK7FU7TU2 866-216-1072,,-10.47,
Chequing,00170-5050885,11/3/2025,,ONLINE BANKING TRANSFER - 7435,,-433.04,
Chequing,00170-5050885,11/4/2025,,E-TRANSFER SENT EGLISE CITE DE LA GRACE INC. FYDQ6R,,-750,
"""


@pytest.fixture
def invalid_csv_content():
    """
    Invalid CSV for testing error handling.
    """
    return """Wrong,Headers,Missing Required Value1,Value2,Value3"""
