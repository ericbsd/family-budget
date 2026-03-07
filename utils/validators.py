"""
Validation utilities for request data.
"""
from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId
from flask import request


def validate_json_request(required_fields: list[str]) -> tuple:
    """
    Validate that request contains JSON data and has required fields.

    Args:
        required_fields: List of required field names

    Returns:
        tuple: (data, error_response) where error_response is None if valid
    """
    from utils.responses import error_response

    data = request.get_json()

    if not data:
        return None, error_response('INVALID_REQUEST', 'Request body must be JSON')

    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return None, error_response(
            'MISSING_FIELDS',
            f'Missing required fields: {", ".join(missing_fields)}',
        )

    return data, None


def validate_category_id(category_id: int, mongo) -> tuple:
    """
    Validate that a category ID exists in the database.

    Args:
        category_id: Category ID to validate
        mongo: Flask-PyMongo instance

    Returns:
        tuple: (is_valid, error_response) where error_response is None if valid
    """
    from utils.responses import error_response

    if not isinstance(category_id, int) or category_id < 0:
        return False, error_response(
            'INVALID_CATEGORY_ID',
            'category_id must be a non-negative integer',
        )

    category_doc = mongo.db.categories.find_one({'id': category_id})
    if not category_doc:
        return False, error_response(
            'INVALID_CATEGORY_ID',
            f'Category ID {category_id} does not exist',
        )

    return True, None


def _validate_date_field(date_value: str) -> datetime:
    """
    Parse and validate a date string from request data.

    Args:
        date_value: Date string in YYYY-MM-DD format

    Returns:
        datetime: Parsed datetime object

    Raises:
        ValueError: If date string does not match YYYY-MM-DD format
    """
    return datetime.strptime(date_value, '%Y-%m-%d')


def _validate_confidence_field(confidence_value: float | int) -> float:
    """
    Validate a confidence score value.

    Args:
        confidence_value: Numeric confidence score to validate

    Returns:
        float: Validated confidence score between 0.0 and 1.0

    Raises:
        ValueError: If value is not between 0.0 and 1.0
    """
    confidence = float(confidence_value)
    if not 0.0 <= confidence <= 1.0:
        raise ValueError('confidence must be between 0.0 and 1.0')
    return confidence


def build_transaction_update_doc(data: dict) -> tuple:
    """
    Build MongoDB update document from request data for transaction updates.

    Args:
        data: Request data dictionary

    Returns:
        tuple: (update_doc, error_response) where error_response is None if valid
    """
    from utils.responses import error_response

    update_doc = {}

    if 'date' in data:
        try:
            update_doc['date'] = _validate_date_field(data['date'])
        except ValueError:
            return None, error_response(
                'VALIDATION_ERROR',
                f'Invalid date format: {data["date"]}. Expected YYYY-MM-DD',
            )

    if 'amount' in data:
        try:
            update_doc['amount'] = float(data['amount'])
        except (ValueError, TypeError):
            return None, error_response(
                'VALIDATION_ERROR',
                f'Invalid amount: {data["amount"]}',
            )

    if 'category_id' in data:
        update_doc['_pending_category_id'] = data['category_id']

    if 'description' in data:
        update_doc['description'] = str(data['description']).strip()

    if 'notes' in data:
        update_doc['notes'] = str(data['notes']).strip()

    if 'auto_categorized' in data:
        update_doc['auto_categorized'] = bool(data['auto_categorized'])

    if 'confidence' in data:
        try:
            update_doc['confidence'] = _validate_confidence_field(data['confidence'])
        except (ValueError, TypeError):
            return None, error_response(
                'VALIDATION_ERROR',
                f'Invalid confidence: {data["confidence"]}',
            )

    return update_doc, None


def validate_update_request(
    resource_id: str,
    collection,
    resource_name: str = 'resource',
) -> tuple:
    """
    Validate common update request requirements.

    Args:
        resource_id: ObjectId string to validate
        collection: MongoDB collection to check existence
        resource_name: Name of resource for error messages (default: "resource")

    Returns:
        tuple: (object_id, data, error_response) where error is None if valid
    """
    from utils.responses import error_response

    try:
        object_id = ObjectId(resource_id)
    except InvalidId:
        return None, None, error_response(
            'INVALID_ID',
            f'Invalid {resource_name} ID format: {resource_id}',
        )

    data = request.get_json()
    if not data:
        return None, None, error_response('INVALID_REQUEST', 'Request body must be JSON')

    document = collection.find_one({'_id': object_id})
    if not document:
        return None, None, error_response(
            'NOT_FOUND',
            f'{resource_name.capitalize()} not found: {resource_id}',
            404,
        )

    return object_id, data, None
