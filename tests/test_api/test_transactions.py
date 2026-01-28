"""
Tests for Transactions API endpoints.
"""
import pytest
from bson import ObjectId

from tests.common import assert_single_item_response


@pytest.mark.api
class TestTransactionsAPI:
    """Test transaction CRUD operations."""

    def test_create_transaction(self, client, db, sample_transaction):
        """Test creating a new transaction."""
        response = client.post('/api/transactions', json=sample_transaction)

        assert response.status_code == 201
        json_data = response.get_json()
        assert json_data['success'] is True
        assert 'Transaction created successfully' in json_data['message']
        assert json_data['data']['description'] == sample_transaction['description']
        assert json_data['data']['amount'] == sample_transaction['amount']

        # Verify in database
        transactions = list(db.transactions.find())
        assert len(transactions) == 1

    def test_create_transaction_missing_fields(self, client):
        """Test creating transaction with missing required fields."""
        incomplete_data = {
            'description': 'Test transaction'
            # Missing date and amount
        }

        response = client.post('/api/transactions', json=incomplete_data)

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'MISSING_FIELDS'

    def test_create_transaction_invalid_category(self, client, sample_transaction):
        """Test creating transaction with non-existent category."""
        sample_transaction['category_id'] = 999  # Non-existent category

        response = client.post('/api/transactions', json=sample_transaction)

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'INVALID_CATEGORY_ID'

    def test_list_transactions(self, client, sample_transaction):
        """Test listing all transactions."""
        # Create a transaction first
        client.post('/api/transactions', json=sample_transaction)

        response = client.get('/api/transactions')
        assert_single_item_response(response)

    def test_list_transactions_with_filters(self, client):
        """Test listing transactions with date and category filters."""
        # Create multiple transactions
        transactions = [
            {
                'date': '2025-11-01',
                'description': 'Transaction 1',
                'amount': -100.00,
                'category_id': 1
            },
            {
                'date': '2025-11-15',
                'description': 'Transaction 2',
                'amount': -200.00,
                'category_id': 1
            },
            {
                'date': '2025-12-01',
                'description': 'Transaction 3',
                'amount': -300.00,
                'category_id': 2
            }
        ]

        for txn in transactions:
            client.post('/api/transactions', json=txn)

        # Filter by date range
        response = client.get('/api/transactions?start_date=2025-11-01&end_date=2025-11-30')
        json_data = response.get_json()
        assert json_data['count'] == 2

        # Filter by category
        response = client.get('/api/transactions?category_id=1')
        json_data = response.get_json()
        assert json_data['count'] == 2

    def test_list_transactions_pagination(self, client):
        """Test transaction list pagination."""
        # Create 15 transactions
        for i in range(15):
            client.post('/api/transactions', json={
                'date': '2025-11-01',
                'description': f'Transaction {i}',
                'amount': -10.00 * i
            })

        # Get first page
        response = client.get('/api/transactions?limit=10&offset=0')
        json_data = response.get_json()
        assert json_data['count'] == 10
        assert json_data['total'] == 15

        # Get second page
        response = client.get('/api/transactions?limit=10&offset=10')
        json_data = response.get_json()
        assert json_data['count'] == 5
        assert json_data['total'] == 15

    def test_get_transaction(self, client, sample_transaction):
        """Test getting a single transaction by ID."""
        # Create transaction
        create_response = client.post('/api/transactions', json=sample_transaction)
        transaction_id = create_response.get_json()['data']['_id']

        # Get transaction
        response = client.get(f'/api/transactions/{transaction_id}')

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert json_data['data']['_id'] == transaction_id
        assert json_data['data']['description'] == sample_transaction['description']

    def test_get_transaction_not_found(self, client):
        """Test getting non-existent transaction."""
        fake_id = str(ObjectId())

        response = client.get(f'/api/transactions/{fake_id}')

        assert response.status_code == 404
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'NOT_FOUND'

    def test_get_transaction_invalid_id(self, client):
        """Test getting transaction with invalid ObjectId format."""
        response = client.get('/api/transactions/invalid-id')

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'INVALID_ID'

    def test_update_transaction(self, client, sample_transaction):
        """Test updating a transaction."""
        # Create transaction
        create_response = client.post('/api/transactions', json=sample_transaction)
        transaction_id = create_response.get_json()['data']['_id']

        # Update transaction
        update_data = {
            'description': 'Updated description',
            'amount': -999.99,
            'category_id': 1
        }

        response = client.put(f'/api/transactions/{transaction_id}', json=update_data)

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert json_data['data']['description'] == 'Updated description'
        assert json_data['data']['amount'] == -999.99
        assert json_data['data']['category_id'] == 1

    def test_update_transaction_not_found(self, client):
        """Test updating non-existent transaction."""
        fake_id = str(ObjectId())
        update_data = {'description': 'Updated'}

        response = client.put(f'/api/transactions/{fake_id}', json=update_data)

        assert response.status_code == 404
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'NOT_FOUND'

    def test_delete_transaction(self, client, db, sample_transaction):
        """Test deleting a transaction."""
        # Create transaction
        create_response = client.post('/api/transactions', json=sample_transaction)
        transaction_id = create_response.get_json()['data']['_id']

        # Delete transaction
        response = client.delete(f'/api/transactions/{transaction_id}')

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert 'deleted successfully' in json_data['message']

        # Verify deleted from database
        transactions = list(db.transactions.find())
        assert len(transactions) == 0

    def test_delete_transaction_not_found(self, client):
        """Test deleting non-existent transaction."""
        fake_id = str(ObjectId())

        response = client.delete(f'/api/transactions/{fake_id}')

        assert response.status_code == 404
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'NOT_FOUND'

    def test_bulk_delete_transactions(self, client, db):
        """Test bulk deleting multiple transactions."""
        # Create 3 transactions
        ids = []
        for i in range(3):
            response = client.post('/api/transactions', json={
                'date': '2025-11-01',
                'description': f'Transaction {i}',
                'amount': -10.00 * i
            })
            ids.append(response.get_json()['data']['_id'])

        # Bulk delete
        response = client.delete('/api/transactions/bulk', json={'ids': ids})

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert json_data['deleted_count'] == 3

        # Verify all deleted
        transactions = list(db.transactions.find())
        assert len(transactions) == 0

    def test_bulk_delete_invalid_ids(self, client):
        """Test bulk delete with invalid IDs."""
        response = client.delete('/api/transactions/bulk', json={
            'ids': ['invalid-id']
        })

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'INVALID_ID'
