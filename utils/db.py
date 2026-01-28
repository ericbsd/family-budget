"""
Database utilities.
MongoDB instance and database access helpers.
"""
from flask_pymongo import PyMongo

# Create MongoDB instance (initialized by app in app.py)
mongo = PyMongo()
