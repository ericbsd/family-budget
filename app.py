"""
Family Budget Application
Main Flask application entry point.
"""
import os
from flask import Flask
from flask_cors import CORS
from pymongo.errors import PyMongoError

from config import config
from utils.db_init import init_db
from utils.db import mongo


def create_app(config_name=None):
    """
    Application factory pattern.
    Creates and configures the Flask application.

    Args:
        config_name: Configuration to use (development, testing, production)
                     Defaults to FLASK_ENV environment variable or 'development'

    Returns:
        Configured Flask application instance
    """
    # Create Flask app
    flask_app = Flask(__name__)

    # Load configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    flask_app.config.from_object(config[config_name])

    # Initialize extensions
    mongo.init_app(flask_app)
    CORS(flask_app)

    # Initialize database (create default categories and indexes)
    with flask_app.app_context():
        init_result = init_db(mongo)
        flask_app.logger.info("Database initialized: %s", init_result)

    # Register blueprints (API routes)
    from api.transactions import transactions_bp
    from api.categories import categories_bp
    from api.upload import upload_bp
    from api.charts import charts_bp
    flask_app.register_blueprint(transactions_bp, url_prefix='/api')
    flask_app.register_blueprint(categories_bp, url_prefix='/api')
    flask_app.register_blueprint(upload_bp, url_prefix='/api')
    flask_app.register_blueprint(charts_bp, url_prefix='/api')

    # Simple health check route
    @flask_app.route('/')
    def index():
        """Health check endpoint."""
        return {
            'status': 'running',
            'message': 'Family Budget API',
            'version': '1.0.0'
        }

    @flask_app.route('/health')
    def health():
        """Detailed health check with MongoDB connection status."""
        try:
            # Test MongoDB connection
            mongo.db.command('ping')
            db_status = 'connected'

            # Get category count
            category_count = mongo.db.categories.count_documents({})
        except PyMongoError as e:
            db_status = f'error: {str(e)}'
            category_count = 0

        return {
            'status': 'ok',
            'database': db_status,
            'environment': config_name,
            'categories': category_count
        }

    @flask_app.route('/api/init-db')
    def manual_init_db():
        """Manually trigger database initialization."""
        result = init_db(mongo)
        return {
            'success': True,
            'data': result,
            'message': 'Database initialization complete'
        }

    return flask_app


# Create an app instance for running directly
app = create_app()


if __name__ == '__main__':
    # Run the development server
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
