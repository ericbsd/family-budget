"""
Tests for CSV upload API endpoints.
"""
import io
import pytest

from tests.common import assert_single_item_response


@pytest.mark.api
class TestUploadCSV:
    """Test CSV upload functionality."""

    def test_upload_valid_bank_csv(self, client, db, bank_csv_content):
        """Test uploading a valid Canadian bank CSV file."""
        # Create file-like object
        data = {
            'file': (io.BytesIO(bank_csv_content.encode('utf-8')), 'bank_transactions.csv')
        }

        # Upload CSV
        response = client.post(
            '/api/upload/csv',
            data=data,
            content_type='multipart/form-data'
        )

        # Assert successful upload
        assert response.status_code == 201
        json_data = response.get_json()
        assert json_data['success'] is True
        assert 'Successfully imported' in json_data['message']
        assert json_data['data']['total_rows'] == 6
        assert json_data['data']['filename'] == 'bank_transactions.csv'

        # Verify transactions were saved to database
        transactions = list(db.transactions.find())
        assert len(transactions) == 6

        # Verify upload record was created
        uploads = list(db.uploads.find())
        assert len(uploads) == 1
        assert uploads[0]['filename'] == 'bank_transactions.csv'
        assert uploads[0]['row_count'] == 6
        assert uploads[0]['status'] == 'processed'

    def test_upload_no_file_provided(self, client):
        """Test upload endpoint with no file."""
        response = client.post('/api/upload/csv')

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'NO_FILE'

    def test_upload_empty_filename(self, client):
        """Test upload with empty filename."""
        data = {
            'file': (io.BytesIO(b''), '')
        }

        response = client.post(
            '/api/upload/csv',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'EMPTY_FILENAME'

    def test_upload_invalid_file_type(self, client):
        """Test upload with non-CSV/TXT file (e.g., PDF, Excel)."""
        data = {
            'file': (io.BytesIO(b'test content'), 'document.pdf')
        }

        response = client.post(
            '/api/upload/csv',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'INVALID_FILE_TYPE'

    def test_upload_invalid_csv_format(self, client, invalid_csv_content):
        """Test upload with invalid CSV format (missing required columns)."""
        data = {
            'file': (io.BytesIO(invalid_csv_content.encode('utf-8')), 'invalid.csv')
        }

        response = client.post(
            '/api/upload/csv',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'INVALID_CSV'

    def test_validate_csv_valid(self, client, bank_csv_content):
        """Test CSV validation endpoint with valid file."""
        data = {
            'file': (io.BytesIO(bank_csv_content.encode('utf-8')), 'test.csv')
        }

        response = client.post(
            '/api/upload/validate',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert 'headers' in json_data['data']
        assert 'column_mapping' in json_data['data']

    def test_validate_csv_invalid(self, client, invalid_csv_content):
        """Test CSV validation endpoint with invalid file."""
        data = {
            'file': (io.BytesIO(invalid_csv_content.encode('utf-8')), 'invalid.csv')
        }

        response = client.post(
            '/api/upload/validate',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert json_data['error']['code'] == 'INVALID_CSV'

    def test_list_uploads(self, client, bank_csv_content):
        """Test listing upload history."""
        # First upload a file
        data = {
            'file': (io.BytesIO(bank_csv_content.encode('utf-8')), 'test.csv')
        }
        client.post('/api/upload/csv', data=data, content_type='multipart/form-data')

        # List uploads
        response = client.get('/api/uploads')
        json_data = assert_single_item_response(response)
        assert json_data['data'][0]['filename'] == 'test.csv'

    def test_get_upload_details(self, client, db, bank_csv_content):
        """Test getting details of a specific upload."""
        # First upload a file
        data = {
            'file': (io.BytesIO(bank_csv_content.encode('utf-8')), 'test.csv')
        }
        client.post(
            '/api/upload/csv',
            data=data,
            content_type='multipart/form-data'
        )

        # Get upload ID from database
        upload = db.uploads.find_one()
        upload_id = str(upload['_id'])

        # Get upload details
        response = client.get(f'/api/uploads/{upload_id}')

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert json_data['data']['filename'] == 'test.csv'
        assert json_data['data']['row_count'] == 6
        assert 'errors' in json_data['data']
