"""
API Response Utilities
Standardized response helpers to eliminate code duplication.
"""
from flask import jsonify


def error_response(code, message, status_code=400):
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
            'message': message
        }
    }), status_code


def success_response(data=None, message=None, status_code=200, **kwargs):
    """
    Create standardized success response.

    Args:
        data: Response data
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

    # Add any additional fields
    response.update(kwargs)

    return jsonify(response), status_code
