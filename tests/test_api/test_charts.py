"""
Tests for Charts API endpoints.
"""
import pytest


@pytest.mark.api
class TestChartsAPI:
    """Test chart data aggregation endpoints."""

    @pytest.fixture
    def _sample_transactions(self, client):
        """Create sample transactions for chart testing."""
        transactions = [
            # November 2025 - Groceries
            {'date': '2025-11-05', 'description': 'COSTCO', 'amount': -150.00, 'category_id': 1},
            {'date': '2025-11-12', 'description': 'WALMART', 'amount': -80.00, 'category_id': 1},
            # November 2025 - Gas
            {'date': '2025-11-07', 'description': 'SHELL GAS', 'amount': -45.00, 'category_id': 2},
            # November 2025 - Entertainment
            {'date': '2025-11-15', 'description': 'NETFLIX', 'amount': -15.99, 'category_id': 4},
            # December 2025 - Groceries
            {'date': '2025-12-03', 'description': 'COSTCO', 'amount': -200.00, 'category_id': 1},
            # December 2025 - Gas
            {'date': '2025-12-10', 'description': 'SHELL GAS', 'amount': -50.00, 'category_id': 2},
        ]

        for txn in transactions:
            client.post('/api/transactions', json=txn)

    def test_monthly_chart(self, client, _sample_transactions):
        """Test getting monthly spending breakdown."""
        response = client.get('/api/charts/monthly/2025/11')

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert json_data['year'] == 2025
        assert json_data['month'] == 11
        assert json_data['count'] > 0

        # Verify category totals
        data_by_category = {item['category']: item['total'] for item in json_data['data']}
        assert data_by_category.get('Groceries') == -230.00  # 150 + 80
        assert data_by_category.get('Gas') == -45.00

    def test_monthly_chart_invalid_month(self, client):
        """Test monthly chart with invalid month number."""
        response = client.get('/api/charts/monthly/2025/13')  # Invalid month

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'INVALID_MONTH'

    def test_quarterly_chart(self, client, _sample_transactions):
        """Test getting quarterly spending breakdown."""
        response = client.get('/api/charts/quarterly/2025/4')  # Q4: Oct-Dec

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert json_data['year'] == 2025
        assert json_data['quarter'] == 4
        assert json_data['count'] > 0

        # Should include both November and December transactions
        data_by_category = {item['category']: item['total'] for item in json_data['data']}
        assert data_by_category.get('Groceries') == -430.00  # 150 + 80 + 200

    def test_quarterly_chart_invalid_quarter(self, client):
        """Test quarterly chart with invalid quarter number."""
        response = client.get('/api/charts/quarterly/2025/5')  # Invalid quarter

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'INVALID_QUARTER'

    def test_annual_chart(self, client, _sample_transactions):
        """Test getting annual spending breakdown."""
        response = client.get('/api/charts/annual/2025')

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert json_data['year'] == 2025
        assert json_data['count'] > 0

        # Should include all 2025 transactions
        total_spending = sum(item['total'] for item in json_data['data'])
        assert total_spending == -540.99  # Sum of all transactions

    def test_budget_status(self, client, db, _sample_transactions):
        """Test getting budget status (actual vs limit)."""
        # Set monthly limit for Groceries
        db.categories.update_one(
            {'id': 1},
            {'$set': {'monthly_limit': 300.00}}
        )

        response = client.get('/api/budget/status/2025/11')

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True

        # Find Groceries in response
        groceries = next((item for item in json_data['data'] if item['category'] == 'Groceries'), None)
        assert groceries is not None
        assert groceries['budget'] == 300.00
        assert groceries['actual'] == 230.00  # Absolute value
        assert groceries['remaining'] == 70.00
        assert groceries['percentage'] < 100  # Under budget
        assert groceries['status'] in ['ok', 'warning']

    def test_budget_status_over_budget(self, client, db, _sample_transactions):
        """Test budget status when over budget."""
        # Set monthly limit lower than actual spending
        db.categories.update_one(
            {'id': 1},
            {'$set': {'monthly_limit': 200.00}}  # Less than actual 230
        )

        response = client.get('/api/budget/status/2025/11')

        assert response.status_code == 200
        json_data = response.get_json()

        # Find Groceries in response
        groceries = next((item for item in json_data['data'] if item['category'] == 'Groceries'), None)
        assert groceries['percentage'] > 100  # Over budget
        assert groceries['status'] == 'over'

    def test_spending_trend(self, client, _sample_transactions):
        """Test getting spending trend over months."""
        response = client.get('/api/charts/trend?year=2025&months=3')

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert json_data['year'] == 2025
        assert json_data['months'] == 3
        assert len(json_data['data']) <= 3  # Up to 3 months of data

    def test_spending_trend_invalid_params(self, client):
        """Test spending trend with invalid parameters."""
        response = client.get('/api/charts/trend?months=50')  # Invalid: too many months

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'INVALID_PARAMETER'

    def test_top_merchants(self, client, _sample_transactions):
        """Test getting top merchants by spending."""
        response = client.get('/api/charts/top-merchants?year=2025&limit=5')

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert json_data['year'] == 2025
        assert len(json_data['data']) <= 5  # Limit to 5

        # Verify merchants are sorted by spending (descending)
        if len(json_data['data']) > 1:
            totals = [abs(item['total']) for item in json_data['data']]
            assert totals == sorted(totals, reverse=True)  # Should be in descending order

    def test_top_merchants_with_month(self, client, _sample_transactions):
        """Test top merchants filtered by month."""
        response = client.get('/api/charts/top-merchants?year=2025&month=11&limit=3')

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert json_data['month'] == 11

        # Should only include November transactions
        merchant_names = [item['merchant'] for item in json_data['data']]
        assert len(merchant_names) <= 3

    def test_top_merchants_invalid_limit(self, client):
        """Test top merchants with invalid limit."""
        response = client.get('/api/charts/top-merchants?limit=200')  # Exceeds max 100

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'INVALID_PARAMETER'
