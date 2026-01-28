"""
Categories API Blueprint
Handles CRUD operations for budget categories.
"""
from flask import Blueprint, request, current_app
from pymongo.errors import PyMongoError

from models.category import Category
from utils.db import mongo
from utils.responses import error_response, success_response
from utils.validators import validate_json_request

categories_bp = Blueprint('categories', __name__)


@categories_bp.route('/categories', methods=['GET'])
def list_categories():
    """
    List all categories.

    Returns:
        JSON response with all categories
    """
    try:
        categories = list(mongo.db.categories.find())

        # Convert to JSON-serializable format
        categories_json = [Category.to_json(cat) for cat in categories]

        return success_response(data=categories_json, count=len(categories_json))

    except PyMongoError as e:
        current_app.logger.error(f"Database error listing categories: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to retrieve categories', 500)


@categories_bp.route('/categories/<int:category_id>', methods=['GET'])
def get_category(category_id):
    """
    Get a single category by ID.

    Args:
        category_id: Category ID (integer)

    Returns:
        JSON response with category data
    """
    try:
        category = mongo.db.categories.find_one({'id': category_id})

        if not category:
            return error_response('NOT_FOUND', f'Category not found: {category_id}', 404)

        return success_response(data=Category.to_json(category))

    except PyMongoError as e:
        current_app.logger.error(f"Database error getting category {category_id}: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to retrieve category', 500)


@categories_bp.route('/categories', methods=['POST'])
def create_category():
    """
    Create a new category.

    Request body:
        {
            "name": "Category Name",
            "description": "Category description",
            "color": "#4CAF50",
            "monthly_limit": 500.00
        }

    Returns:
        JSON response with created category
    """
    try:
        # Validate request
        data, error = validate_json_request(['name', 'description', 'color'])
        if error:
            return error

        # Check if category name already exists
        existing = mongo.db.categories.find_one({'name': data['name'].strip()})
        if existing:
            return error_response('DUPLICATE_NAME',
                                f'Category with name "{data["name"]}" already exists',
                                409)

        # Generate next category ID
        next_id = Category.get_next_id(mongo)

        # Create category document
        try:
            category = Category.create(
                category_id=next_id,
                name=data['name'],
                description=data['description'],
                color=data['color'],
                monthly_limit=data.get('monthly_limit', 0.0)
            )
        except ValueError as e:
            return error_response('VALIDATION_ERROR', str(e))

        # Insert into database
        result = mongo.db.categories.insert_one(category)
        category['_id'] = result.inserted_id

        current_app.logger.info(f"Created category: {data['name']} with ID {next_id}")

        return success_response(
            data=Category.to_json(category),
            message=f'Category "{data["name"]}" created successfully',
            status_code=201
        )

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))
    except PyMongoError as e:
        current_app.logger.error(f"Database error creating category: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to create category', 500)


@categories_bp.route('/categories/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    """
    Update an existing category.
    Only name, description, color, and monthly_limit can be updated.
    The category ID cannot be changed.

    Args:
        category_id: Category ID (integer)

    Request body:
        {
            "name": "Updated name",
            "description": "Updated description",
            "color": "#FF5722",
            "monthly_limit": 600.00
        }

    Returns:
        JSON response with updated category
    """
    try:
        data = request.get_json()

        if not data:
            return error_response('INVALID_REQUEST', 'Request body must be JSON')

        # Check if category exists
        category = mongo.db.categories.find_one({'id': category_id})
        if not category:
            return error_response('NOT_FOUND', f'Category not found: {category_id}', 404)

        # Create update document
        try:
            update_doc = Category.update(category_id, **data)
        except ValueError as e:
            return error_response('VALIDATION_ERROR', str(e))

        if not update_doc or '$set' not in update_doc or not update_doc['$set']:
            return error_response('NO_UPDATES', 'No valid fields to update')

        # Update in database
        mongo.db.categories.update_one({'id': category_id}, update_doc)

        # Fetch updated category
        updated_category = mongo.db.categories.find_one({'id': category_id})

        current_app.logger.info(f"Updated category ID {category_id}: {updated_category['name']}")

        return success_response(
            data=Category.to_json(updated_category),
            message=f'Category "{updated_category["name"]}" updated successfully'
        )

    except PyMongoError as e:
        current_app.logger.error(f"Database error updating category {category_id}: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to update category', 500)


@categories_bp.route('/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    """
    Delete a category.

    Args:
        category_id: Category ID (integer)

    Returns:
        JSON response confirming deletion
    """
    try:
        # Check if category exists
        category = mongo.db.categories.find_one({'id': category_id})
        if not category:
            return error_response('NOT_FOUND', f'Category not found: {category_id}', 404)

        # Check if category is in use by any transactions
        transaction_count = mongo.db.transactions.count_documents({'category_id': category_id})
        if transaction_count > 0:
            return error_response('CATEGORY_IN_USE',
                                (f'Cannot delete category "{category["name"]}" (ID {category_id}) - '
                                 f'it is used by {transaction_count} transaction(s)'),
                                409)

        # Delete category
        mongo.db.categories.delete_one({'id': category_id})

        current_app.logger.info(f"Deleted category ID {category_id}: {category['name']}")

        return success_response(message=f'Category "{category["name"]}" deleted successfully')

    except PyMongoError as e:
        current_app.logger.error(f"Database error deleting category {category_id}: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to delete category', 500)
