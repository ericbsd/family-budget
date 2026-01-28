"""
Test helper functions for common assertions and operations.
"""


def assert_single_item_response(response):
    """
    Assert that API response contains exactly one item.

    Args:
        response: Flask test client response object

    Returns:
        dict: The JSON response data
    """
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['success'] is True
    assert json_data['count'] == 1
    assert json_data['total'] == 1
    assert len(json_data['data']) == 1
    return json_data
