"""
Upload API Blueprint
Handles CSV file uploads and transaction import.
"""

from datetime import datetime, timezone
from flask import Blueprint, request, current_app
from werkzeug.utils import secure_filename
from pymongo.errors import PyMongoError

from models.transaction import Transaction
from utils.csv_parser import CSVParser
from utils.categorization import AutoCategorizer
from utils.db import mongo
from utils.responses import error_response, success_response

upload_bp = Blueprint('upload', __name__)


def _validate_uploaded_file():
    """
    Validate uploaded file and return file content and filename.

    Returns:
        tuple: (file_content, filename, error_response) where error is None if valid
    """
    # Check if file is in request
    if 'file' not in request.files:
        return None, None, error_response('NO_FILE', 'No file provided in request')

    file = request.files['file']

    # Check if filename is empty
    if file.filename == '':
        return None, None, error_response('EMPTY_FILENAME', 'No file selected')

    # Check file extension
    if not allowed_file(file.filename):
        return None, None, error_response('INVALID_FILE_TYPE', 'Only CSV files are allowed')

    # Read file content
    file_content = file.read().decode('utf-8')
    filename = secure_filename(file.filename)

    # Validate CSV
    validation = CSVParser.validate_csv(file_content)
    if not validation['valid']:
        return None, None, error_response('INVALID_CSV', validation['error'])

    return file_content, filename, None


def _process_transactions(parse_result, filename, categorizer):
    """
    Process and save transactions from parsed CSV.

    Returns:
        tuple: (saved_count, categorized_count, uncategorized_count)
    """
    categorized_count = 0
    uncategorized_count = 0

    for txn_data in parse_result['transactions']:
        # Auto-categorize
        categorization = categorizer.categorize(txn_data['description'])

        # Create and save transaction
        transaction = Transaction.create(
            date=txn_data['date'],
            description=txn_data['description'],
            amount=txn_data['amount'],
            category_id=categorization['category_id'],
            source_file=filename,
            auto_categorized=(categorization['match_type'] != 'none'),
            confidence=categorization['confidence']
        )

        mongo.db.transactions.insert_one(transaction)

        # Update counters
        if categorization['match_type'] != 'none':
            categorized_count += 1
        else:
            uncategorized_count += 1

    return parse_result['row_count'], categorized_count, uncategorized_count


def allowed_file(filename):
    """
    Check if file extension is allowed.

    Args:
        filename: Filename to check

    Returns:
        bool: True if allowed
    """
    allowed_extensions = {'csv', 'txt'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


@upload_bp.route('/upload/csv', methods=['POST'])
def upload_csv():
    """
    Upload and process CSV file.

    Request:
        multipart/form-data with 'file' field

    Returns:
        JSON response with upload results
    """
    try:
        # Validate uploaded file
        file_content, filename, error = _validate_uploaded_file()
        if error:
            return error

        # Parse CSV
        try:
            parse_result = CSVParser.parse_csv(file_content, filename)
        except (ValueError, UnicodeDecodeError, KeyError) as e:
            current_app.logger.error(f"CSV parsing error: {str(e)}")
            return error_response('PARSE_ERROR', f'Error parsing CSV: {str(e)}')

        if parse_result['row_count'] == 0:
            return error_response('NO_DATA', 'No valid transactions found in CSV')

        # Process and save transactions
        categorizer = AutoCategorizer(mongo)
        row_count, categorized_count, uncategorized_count = _process_transactions(
            parse_result, filename, categorizer
        )

        # Determine month from first transaction
        month = (parse_result['transactions'][0]['date'].strftime('%Y-%m')
                 if parse_result['transactions']
                 else datetime.now(timezone.utc).strftime('%Y-%m'))

        # Record upload metadata
        mongo.db.uploads.insert_one({
            'filename': filename,
            'upload_date': datetime.now(timezone.utc),
            'row_count': row_count,
            'month': month,
            'status': 'processed',
            'categorized_count': categorized_count,
            'uncategorized_count': uncategorized_count,
            'errors': parse_result['errors'],
        })

        current_app.logger.info(
            f"Uploaded {filename}: {row_count} transactions, "
            f"{categorized_count} auto-categorized, {uncategorized_count} uncategorized"
        )

        return success_response(
            data={
                'filename': filename,
                'total_rows': row_count,
                'categorized': categorized_count,
                'uncategorized': uncategorized_count,
                'month': month,
                'errors': parse_result['errors']
            },
            message=f'Successfully imported {row_count} transactions',
            status_code=201
        )

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))
    except PyMongoError as e:
        current_app.logger.error(f"Database error during upload: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to save uploaded transactions', 500)


@upload_bp.route('/upload/validate', methods=['POST'])
def validate_csv():
    """
    Validate CSV file without importing.
    Quick check to see if file format is correct.

    Request:
        multipart/form-data with 'file' field

    Returns:
        JSON response with validation results
    """
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return error_response('NO_FILE', 'No file provided in request')

        file = request.files['file']

        if file.filename == '':
            return error_response('EMPTY_FILENAME', 'No file selected')

        if not allowed_file(file.filename):
            return error_response('INVALID_FILE_TYPE', 'Only CSV files are allowed')

        # Read and validate
        file_content = file.read().decode('utf-8')
        validation = CSVParser.validate_csv(file_content)

        if validation['valid']:
            return success_response(
                data={
                    'headers': validation['headers'],
                    'column_mapping': validation['column_mapping']
                },
                message='CSV file is valid'
            )

        return error_response('INVALID_CSV', validation['error'])

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))


@upload_bp.route('/uploads', methods=['GET'])
def list_uploads():
    """
    List upload history.

    Query parameters:
        limit: Maximum number of results (default: 50)
        offset: Number of results to skip (default: 0)

    Returns:
        JSON response with upload history
    """
    try:

        # Pagination
        try:
            limit = int(request.args.get('limit', 50))
            offset = int(request.args.get('offset', 0))
        except ValueError:
            return error_response('INVALID_PAGINATION', 'limit and offset must be integers')

        # Get uploads
        uploads = list(
            mongo.db.uploads
            .find()
            .sort('upload_date', -1)
            .skip(offset)
            .limit(limit)
        )

        # Convert to JSON-serializable format
        uploads_json = []
        for upload in uploads:
            upload_dict = {
                '_id': str(upload['_id']),
                'filename': upload['filename'],
                'upload_date': upload['upload_date'].isoformat(),
                'row_count': upload['row_count'],
                'month': upload['month'],
                'status': upload['status'],
                'categorized_count': upload['categorized_count'],
                'uncategorized_count': upload['uncategorized_count']
            }

            if 'errors' in upload and upload['errors']:
                upload_dict['error_count'] = len(upload['errors'])

            uploads_json.append(upload_dict)

        # Get total count
        total_count = mongo.db.uploads.count_documents({})

        return success_response(
            data=uploads_json,
            count=len(uploads_json),
            total=total_count,
            limit=limit,
            offset=offset
        )

    except PyMongoError as e:
        current_app.logger.error(f"Database error listing uploads: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to retrieve upload history', 500)


@upload_bp.route('/uploads/<upload_id>', methods=['GET'])
def get_upload_details(upload_id):
    """
    Get detailed information about a specific upload.

    Args:
        upload_id: Upload ObjectId as string

    Returns:
        JSON response with upload details including errors
    """
    try:
        from bson import ObjectId
        from bson.errors import InvalidId

        # Validate ObjectId
        try:
            object_id = ObjectId(upload_id)
        except InvalidId:
            return error_response('INVALID_ID', f'Invalid upload ID format: {upload_id}')

        upload = mongo.db.uploads.find_one({'_id': object_id})

        if not upload:
            return error_response('NOT_FOUND', f'Upload not found: {upload_id}', 404)

        # Convert to JSON-serializable format
        upload_json = {
            '_id': str(upload['_id']),
            'filename': upload['filename'],
            'upload_date': upload['upload_date'].isoformat(),
            'row_count': upload['row_count'],
            'month': upload['month'],
            'status': upload['status'],
            'categorized_count': upload['categorized_count'],
            'uncategorized_count': upload['uncategorized_count'],
            'errors': upload.get('errors', [])
        }

        return success_response(data=upload_json)

    except PyMongoError as e:
        current_app.logger.error(f"Database error getting upload {upload_id}: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to retrieve upload details', 500)
