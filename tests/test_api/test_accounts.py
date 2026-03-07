"""
Tests for Accounts API endpoints.
"""
import pytest


@pytest.mark.api
class TestAccountsAPI:
    """Test account CRUD operations."""

    # ── GET /api/accounts ──────────────────────────────────────────

    def test_list_accounts_returns_seeded_account(self, client):
        """Test that GET /api/accounts returns the seeded default account."""
        response = client.get('/api/accounts')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['count'] == 1
        accounts = data['data']
        assert accounts[0]['id'] == 1
        assert accounts[0]['name'] == 'Chequing'

    def test_list_accounts_ordered_by_id(self, client):
        """Test that accounts are returned sorted by ID ascending."""
        client.post('/api/accounts', json={'name': 'Savings', 'type': 'savings'})
        client.post('/api/accounts', json={'name': 'Visa', 'type': 'credit_card'})

        response = client.get('/api/accounts')
        data = response.get_json()
        ids = [account['id'] for account in data['data']]
        assert ids == sorted(ids)

    def test_list_accounts_uses_to_json_serialization(self, client):
        """Test that response fields come from Account.to_json serialization."""
        response = client.get('/api/accounts')
        account = response.get_json()['data'][0]
        assert 'id' in account
        assert 'name' in account
        assert 'type' in account
        # doc_to_json converts ObjectId to a string — verify it is a plain string
        assert isinstance(account.get('_id'), str)

    # ── GET /api/accounts/<id> ─────────────────────────────────────

    def test_get_account_found(self, client):
        """Test retrieving an existing account by ID."""
        response = client.get('/api/accounts/1')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['id'] == 1

    def test_get_account_not_found(self, client):
        """Test retrieving a non-existent account returns 404."""
        response = client.get('/api/accounts/999')

        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert data['error']['code'] == 'NOT_FOUND'

    # ── POST /api/accounts ─────────────────────────────────────────

    def test_create_account_success(self, client):
        """Test creating a new account with valid data."""
        payload = {
            'name': 'TD Savings',
            'type': 'savings',
            'institution': 'TD Bank',
            'color': '#4CAF50',
            'currency': 'CAD',
        }
        response = client.post('/api/accounts', json=payload)

        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['name'] == 'TD Savings'
        assert data['data']['type'] == 'savings'

    def test_create_account_missing_name(self, client):
        """Test that creating an account without a name returns 400."""
        response = client.post('/api/accounts', json={'type': 'checking'})

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['error']['code'] == 'INVALID_REQUEST'

    def test_create_account_missing_type(self, client):
        """Test that creating an account without a type returns 400."""
        response = client.post('/api/accounts', json={'name': 'My Account'})

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['error']['code'] == 'INVALID_REQUEST'

    def test_create_account_invalid_type(self, client):
        """Test that creating an account with an invalid type returns 400."""
        response = client.post(
            '/api/accounts',
            json={'name': 'My Account', 'type': 'not_a_real_type'},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['error']['code'] == 'VALIDATION_ERROR'

    # ── PUT /api/accounts/<id> ─────────────────────────────────────

    def test_update_account_success(self, client):
        """Test updating allowed fields on an existing account."""
        response = client.put(
            '/api/accounts/1',
            json={'name': 'Updated Chequing', 'institution': 'TD Bank'},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['name'] == 'Updated Chequing'
        assert data['data']['institution'] == 'TD Bank'

    def test_update_account_not_found(self, client):
        """Test updating a non-existent account returns 404."""
        response = client.put('/api/accounts/999', json={'name': 'Ghost'})

        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert data['error']['code'] == 'NOT_FOUND'

    def test_update_account_no_valid_fields(self, client):
        """Test that sending only disallowed fields returns NO_UPDATES error."""
        response = client.put('/api/accounts/1', json={'id': 99, 'type': 'savings'})

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['error']['code'] == 'NO_UPDATES'

    def test_update_account_no_body(self, client):
        """Test that an empty request body returns INVALID_REQUEST error."""
        response = client.put('/api/accounts/1', json={})

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['error']['code'] == 'INVALID_REQUEST'

    # ── DELETE /api/accounts/<id> ──────────────────────────────────

    def test_delete_account_success(self, client):
        """Test deleting an account that has no associated transactions."""
        client.post('/api/accounts', json={'name': 'Temp Account', 'type': 'savings'})
        response = client.get('/api/accounts')
        new_account_id = next(
            account['id'] for account in response.get_json()['data']
            if account['name'] == 'Temp Account'
        )

        delete_response = client.delete(f'/api/accounts/{new_account_id}')

        assert delete_response.status_code == 200
        data = delete_response.get_json()
        assert data['success'] is True

    def test_delete_account_not_found(self, client):
        """Test deleting a non-existent account returns 404."""
        response = client.delete('/api/accounts/999')

        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert data['error']['code'] == 'NOT_FOUND'

    def test_delete_account_in_use(self, client):
        """Test that deleting an account referenced by transactions returns 409."""
        from datetime import datetime, UTC
        from utils.db import mongo
        from flask import current_app

        with current_app.app_context():
            mongo.db.transactions.insert_one({
                'date': datetime.now(UTC),
                'description': 'Test transaction',
                'amount': -50.0,
                'category_id': 0,
                'account_id': 1,
                'notes': '',
                'auto_categorized': False,
                'confidence': 0.0,
            })

        response = client.delete('/api/accounts/1')

        assert response.status_code == 409
        data = response.get_json()
        assert data['success'] is False
        assert data['error']['code'] == 'ACCOUNT_IN_USE'
