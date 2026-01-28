"""
Configuration file for Family Budget application.
Loads settings from environment variables (via .env file in development).
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file (development only)
load_dotenv()


@dataclass
# pylint: disable=too-few-public-methods,invalid-name
class Config:
    """Base configuration class."""
    # Flask settings
    SECRET_KEY: str = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    # MongoDB settings
    MONGO_URI: str = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/budget_app'
    # Flask-CORS settings
    CORS_HEADERS: str = 'Content-Type'
    # Application settings
    DEBUG: bool = os.environ.get('FLASK_ENV') == 'development'
    TESTING: bool = False


@dataclass
# pylint: disable=too-few-public-methods
class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG: bool = True
    TESTING: bool = False


@dataclass
# pylint: disable=too-few-public-methods
class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING: bool = True
    MONGO_URI: str = 'mongodb://localhost:27017/budget_app_test'


@dataclass
# pylint: disable=too-few-public-methods
class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG: bool = False
    TESTING: bool = False
    # In production, SECRET_KEY must be set via an environment variable
    SECRET_KEY: str = os.environ.get('SECRET_KEY')


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
