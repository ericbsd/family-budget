"""
Tests for Categories API endpoints.
"""
import pytest


@pytest.mark.api
class TestCategoriesAPI:
    """Test category CRUD operations."""

    def test_list_categories(self, client):
        """Test listing all categories (should have 7 defaults)."""
        response = client.get('/api/categories')

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert json_data['count'] == 7  # 7 default categories
        assert len(json_data['data']) == 7

        # Verify default categories exist
        category_names = [cat['name'] for cat in json_data['data']]
        assert 'Uncategorized' in category_names
        assert 'Groceries' in category_names
        assert 'Gas' in category_names

    def test_get_category_by_id(self, client):
        """Test getting a specific category by ID."""
        # Get Groceries (ID 1)
        response = client.get('/api/categories/1')

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert json_data['data']['id'] == 1
        assert json_data['data']['name'] == 'Groceries'

    def test_get_category_not_found(self, client):
        """Test getting non-existent category."""
        response = client.get('/api/categories/999')

        assert response.status_code == 404
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'NOT_FOUND'

    def test_create_category(self, client, db, sample_category):
        """Test creating a new category."""
        response = client.post('/api/categories', json=sample_category)

        assert response.status_code == 201
        json_data = response.get_json()
        assert json_data['success'] is True
        assert 'created successfully' in json_data['message']
        assert json_data['data']['name'] == sample_category['name']
        assert json_data['data']['color'] == sample_category['color']
        assert json_data['data']['id'] >= 7  # User categories start at ID 7

        # Verify in database
        categories = list(db.categories.find())
        assert len(categories) == 8  # 7 defaults + 1 new

    def test_create_category_missing_fields(self, client):
        """Test creating category with missing required fields."""
        incomplete_data = {
            'name': 'Test Category'
            # Missing description, color
        }

        response = client.post('/api/categories', json=incomplete_data)

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'MISSING_FIELDS'

    def test_create_category_invalid_color(self, client):
        """Test creating category with invalid hex color."""
        invalid_data = {
            'name': 'Test Category',
            'description': 'Test',
            'color': 'not-a-color',  # Invalid hex
            'monthly_limit': 500.00
        }

        response = client.post('/api/categories', json=invalid_data)

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'VALIDATION_ERROR'

    def test_update_category(self, client):
        """Test updating a category."""
        # Update Groceries (ID 1)
        update_data = {
            'name': 'Updated Groceries',
            'monthly_limit': 750.00
        }

        response = client.put('/api/categories/1', json=update_data)

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert json_data['data']['name'] == 'Updated Groceries'
        assert json_data['data']['monthly_limit'] == 750.00

    def test_update_category_not_found(self, client):
        """Test updating non-existent category."""
        response = client.put('/api/categories/999', json={'name': 'Updated'})

        assert response.status_code == 404
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'NOT_FOUND'

    def test_update_category_no_changes(self, client):
        """Test updating category with no valid fields."""
        response = client.put('/api/categories/1', json={})

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'INVALID_REQUEST'  # Empty JSON body

    def test_delete_user_category(self, client, db, sample_category):
        """Test deleting a user-created category (ID >= 7)."""
        # Create a category first
        create_response = client.post('/api/categories', json=sample_category)
        category_id = create_response.get_json()['data']['id']

        # Delete it
        response = client.delete(f'/api/categories/{category_id}')

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert 'deleted successfully' in json_data['message']

        # Verify deleted from database
        category = db.categories.find_one({'id': category_id})
        assert category is None

    def test_delete_category_in_use(self, client, sample_category):
        """Test deleting category that has transactions."""
        # Create category
        create_response = client.post('/api/categories', json=sample_category)
        category_id = create_response.get_json()['data']['id']

        # Create transaction with this category
        client.post('/api/transactions', json={
            'date': '2025-11-01',
            'description': 'Test transaction',
            'amount': -100.00,
            'category_id': category_id
        })

        # Try to delete category
        response = client.delete(f'/api/categories/{category_id}')

        assert response.status_code == 409  # Conflict
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'CATEGORY_IN_USE'

    def test_delete_category_not_found(self, client):
        """Test deleting non-existent category."""
        response = client.delete('/api/categories/999')

        assert response.status_code == 404
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'NOT_FOUND'

    def test_category_auto_increment_id(self, client):
        """Test that new categories get auto-incremented IDs."""
        # Create first user category
        response1 = client.post('/api/categories', json={
            'name': 'Category 1',
            'description': 'First',
            'color': '#FF0000'
        })
        id1 = response1.get_json()['data']['id']

        # Create second user category
        response2 = client.post('/api/categories', json={
            'name': 'Category 2',
            'description': 'Second',
            'color': '#00FF00'
        })
        id2 = response2.get_json()['data']['id']

        # IDs should be sequential
        assert id1 == 7  # First user category
        assert id2 == 8  # Second user category
