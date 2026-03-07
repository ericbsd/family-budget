"""
API Response Utilities
Standardized response helpers to eliminate code duplication.
"""
from datetime import datetime

from flask import jsonify


def doc_to_json(doc: dict) -> dict:
    """
    Convert a MongoDB document to a JSON-serializable dict.

    Converts ObjectId to string and datetime to ISO format string.

    Args:
        doc: dict - MongoDB document

    Returns:
        dict: JSON-serializable copy of the document
    """
    result = doc.copy()
    if '_id' in result:
        result['_id'] = str(result['_id'])
    if 'created_date' in result and isinstance(result['created_date'], datetime):
        result['created_date'] = result['created_date'].isoformat()
    return result


def error_response(code: str, message: str, status_code: int = 400) -> tuple:
    """
    Create standardized error response.

    Args:
        code: Error code string
        message: Error message
        status_code: HTTP status code

    Returns:
        tuple: (JSON response, status code)
    """
    return jsonify({
        'success': False,
        'error': {
            'code': code,
            'message': message,
        }
    }), status_code


def success_response(data=None, message: str = '', status_code: int = 200, **kwargs) -> tuple:
    """
    Create standardized success response.

    Args:
        data: Response data (dict, list, or None)
        message: Optional success message
        status_code: HTTP status code
        **kwargs: Additional fields (count, total, etc.)

    Returns:
        tuple: (JSON response, status code)
    """
    response = {'success': True}

    if data is not None:
        response['data'] = data

    if message:
        response['message'] = message

    response.update(kwargs)

    return jsonify(response), status_code
