"""
Pytest configuration for Playwright UI tests.
Uses pytest-flask's live_server to spin up a real HTTP server.
"""
import os
import pytest

from app import create_app
from utils.db import mongo
from utils.db_init import init_db


@pytest.fixture(scope='session')
def app():
    """Flask app fixture required by pytest-flask's live_server."""
    os.environ['FLASK_ENV'] = 'testing'
    test_app = create_app('testing')
    test_app.config['MONGO_URI'] = 'mongodb://localhost:27017/budget_app_test_ui'
    test_app.config['LIVESERVER_PORT'] = 5099

    with test_app.app_context():
        mongo.cx.drop_database('budget_app_test_ui')
        init_db(mongo)

    yield test_app

    with test_app.app_context():
        mongo.cx.drop_database('budget_app_test_ui')


@pytest.fixture(scope='session')
def base_url(live_server):
    """Override playwright base_url to point at our live Flask server."""
    return live_server.url
