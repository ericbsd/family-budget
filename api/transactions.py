"""
Transactions API Blueprint
Handles CRUD operations for budget transactions.
"""
from datetime import datetime

from flask import Blueprint, request, current_app
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from models.transaction import Transaction
from utils.db import mongo
from utils.responses import error_response, success_response
from utils.validators import (validate_json_request, validate_category_id,
                              build_transaction_update_doc, validate_update_request)

transactions_bp = Blueprint('transactions', __name__)


def parse_date(date_string):
    """
    Parse date string to datetime object.

    Args:
        date_string: Date in format YYYY-MM-DD

    Returns:
        datetime object

    Raises:
        ValueError: If date format is invalid
    """
    try:
        return datetime.strptime(date_string, '%Y-%m-%d')
    except ValueError as exc:
        raise ValueError(f'Invalid date format: {date_string}. Expected YYYY-MM-DD') from exc


@transactions_bp.route('/transactions', methods=['GET'])
def list_transactions():
    """
    List all transactions with optional filters.

    Query parameters:
        start_date: Filter by start date (YYYY-MM-DD)
        end_date: Filter by end date (YYYY-MM-DD)
        category_id: Filter by category ID (integer)
        limit: Maximum number of results (default: 100)
        offset: Number of results to skip (default: 0)
        sort: Sort field (default: date)
        order: Sort order - 'asc' or 'desc' (default: desc)

    Returns:
        JSON response with transactions
    """
    try:

        # Build query filter
        query = {}

        # Date range filter
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if start_date or end_date:
            query['date'] = {}
            if start_date:
                query['date']['$gte'] = parse_date(start_date)
            if end_date:
                # Add one day to include the end date
                end_datetime = parse_date(end_date)
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
                query['date']['$lte'] = end_datetime

        # Category filter
        category_id = request.args.get('category_id')
        if category_id:
            try:
                query['category_id'] = int(category_id)
            except ValueError:
                return error_response('INVALID_CATEGORY_ID', 'category_id must be an integer')

        # Pagination
        try:
            limit = int(request.args.get('limit', 100))
            offset = int(request.args.get('offset', 0))
        except ValueError:
            return error_response('INVALID_PAGINATION', 'limit and offset must be integers')

        # Sort
        sort_field = request.args.get('sort', 'date')
        sort_order = request.args.get('order', 'desc')

        if sort_field not in ['date', 'amount', 'category_id', 'description']:
            sort_field = 'date'

        sort_direction = -1 if sort_order == 'desc' else 1

        # Execute query
        transactions = list(
            mongo.db.transactions
            .find(query)
            .sort(sort_field, sort_direction)
            .skip(offset)
            .limit(limit)
        )

        # Get total count for pagination
        total_count = mongo.db.transactions.count_documents(query)

        # Convert to JSON-serializable format
        transactions_json = [Transaction.to_json(txn) for txn in transactions]

        return success_response(
            data=transactions_json,
            count=len(transactions_json),
            total=total_count,
            limit=limit,
            offset=offset
        )

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))
    except PyMongoError as e:
        current_app.logger.error(f"Database error listing transactions: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to retrieve transactions', 500)


@transactions_bp.route('/transactions/<transaction_id>', methods=['GET'])
def get_transaction(transaction_id):
    """
    Get a single transaction by ID.

    Args:
        transaction_id: Transaction ObjectId as string

    Returns:
        JSON response with transaction data
    """
    try:
        # Validate ObjectId
        try:
            object_id = ObjectId(transaction_id)
        except InvalidId:
            return error_response('INVALID_ID', f'Invalid transaction ID format: {transaction_id}')

        transaction = mongo.db.transactions.find_one({'_id': object_id})

        if not transaction:
            return error_response('NOT_FOUND', f'Transaction not found: {transaction_id}', 404)

        return success_response(data=Transaction.to_json(transaction))

    except PyMongoError as e:
        current_app.logger.error(f"Database error getting transaction {transaction_id}: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to retrieve transaction', 500)


@transactions_bp.route('/transactions', methods=['POST'])
def create_transaction():
    """
    Create a new transaction.

    Request body:
        {
            "date": "2024-12-19" or datetime object,
            "description": "Transaction description",
            "amount": -50.00,
            "category_id": 1,
            "notes": "Optional notes",
            "source_file": "optional.csv"
        }

    Returns:
        JSON response with created transaction
    """
    try:
        # Validate request
        data, error = validate_json_request(['date', 'description', 'amount'])
        if error:
            return error

        # Validate category_id exists if provided (default to 0 = Uncategorized)
        category_id = data.get('category_id', 0)
        is_valid, error = validate_category_id(category_id, mongo)
        if not is_valid:
            return error

        # Create transaction document
        try:
            transaction = Transaction.create(
                date=data['date'],
                description=data['description'],
                amount=data['amount'],
                category_id=category_id,
                source_file=data.get('source_file'),
                notes=data.get('notes', ''),
                auto_categorized=data.get('auto_categorized', False),
                confidence=data.get('confidence', 0.0)
            )
        except ValueError as e:
            return error_response('VALIDATION_ERROR', str(e))

        # Insert into database
        result = mongo.db.transactions.insert_one(transaction)
        transaction['_id'] = result.inserted_id

        current_app.logger.info(f"Created transaction: {data['description']}")

        return success_response(
            data=Transaction.to_json(transaction),
            message='Transaction created successfully',
            status_code=201
        )

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))
    except PyMongoError as e:
        current_app.logger.error(f"Database error creating transaction: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to create transaction', 500)


@transactions_bp.route('/transactions/<transaction_id>', methods=['PUT'])
def update_transaction(transaction_id):
    """
    Update an existing transaction.

    Args:
        transaction_id: Transaction ObjectId as string

    Request body:
        {
            "date": "2024-12-19",
            "description": "Updated description",
            "amount": -60.00,
            "category_id": 2,
            "notes": "Updated notes"
        }

    Returns:
        JSON response with updated transaction
    """
    try:
        # Validate request and check transaction exists
        object_id, data, error = validate_update_request(
            transaction_id, mongo.db.transactions, "transaction"
        )
        if error:
            return error

        # Build update document
        update_doc, error = build_transaction_update_doc(data)
        if error:
            return error

        # Validate and add category_id if provided
        if '_pending_category_id' in update_doc:
            category_id = update_doc.pop('_pending_category_id')
            is_valid, error = validate_category_id(category_id, mongo)
            if not is_valid:
                return error
            update_doc['category_id'] = category_id

        if not update_doc:
            return error_response('NO_UPDATES', 'No valid fields to update')

        # Update in database
        mongo.db.transactions.update_one({'_id': object_id}, {'$set': update_doc})

        # Fetch updated transaction
        updated_transaction = mongo.db.transactions.find_one({'_id': object_id})

        # Batch categorization: If category was updated, learn from it and update similar transactions
        batch_count = 0
        if 'category_id' in update_doc and update_doc['category_id'] != 0:
            from utils.categorization import AutoCategorizer
            categorizer = AutoCategorizer(mongo)

            # Learn from this categorization
            categorizer.learn_from_categorization(
                updated_transaction['description'],
                update_doc['category_id']
            )

            # Batch categorize all matching uncategorized transactions
            batch_count = categorizer.batch_categorize_similar(
                updated_transaction['description'],
                update_doc['category_id']
            )

            if batch_count > 0:
                current_app.logger.info(
                    f"Batch categorized {batch_count} similar transactions to category {update_doc['category_id']}"
                )

        current_app.logger.info(f"Updated transaction: {transaction_id}")

        message = 'Transaction updated successfully'
        if batch_count > 0:
            message += f' ({batch_count} similar transaction(s) also categorized)'

        return success_response(
            data=Transaction.to_json(updated_transaction),
            message=message,
            batch_categorized=batch_count
        )

    except PyMongoError as e:
        current_app.logger.error(f"Database error updating transaction {transaction_id}: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to update transaction', 500)


@transactions_bp.route('/transactions/<transaction_id>', methods=['DELETE'])
def delete_transaction(transaction_id):
    """
    Delete a transaction.

    Args:
        transaction_id: Transaction ObjectId as string

    Returns:
        JSON response confirming deletion
    """
    try:
        # Validate ObjectId
        try:
            object_id = ObjectId(transaction_id)
        except InvalidId:
            return error_response('INVALID_ID', f'Invalid transaction ID format: {transaction_id}')

        # Check if transaction exists
        transaction = mongo.db.transactions.find_one({'_id': object_id})
        if not transaction:
            return error_response('NOT_FOUND', f'Transaction not found: {transaction_id}', 404)

        # Delete transaction
        mongo.db.transactions.delete_one({'_id': object_id})

        current_app.logger.info(f"Deleted transaction: {transaction_id}")

        return success_response(message='Transaction deleted successfully')

    except PyMongoError as e:
        current_app.logger.error(f"Database error deleting transaction {transaction_id}: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to delete transaction', 500)


@transactions_bp.route('/transactions/bulk', methods=['DELETE'])
def bulk_delete_transactions():
    """
    Delete multiple transactions.

    Request body:
        {
            "ids": ["id1", "id2", "id3"]
        }

    Returns:
        JSON response with deletion count
    """
    try:
        data = request.get_json()

        if not data or 'ids' not in data:
            return error_response('INVALID_REQUEST', 'Request body must contain "ids" array')

        if not isinstance(data['ids'], list):
            return error_response('INVALID_REQUEST', '"ids" must be an array')

        # Convert string IDs to ObjectIds
        object_ids = []
        for tid in data['ids']:
            try:
                object_ids.append(ObjectId(tid))
            except InvalidId:
                return error_response('INVALID_ID', f'Invalid transaction ID format: {tid}')

        # Delete transactions
        result = mongo.db.transactions.delete_many({'_id': {'$in': object_ids}})

        current_app.logger.info(f"Bulk deleted {result.deleted_count} transactions")

        return success_response(
            deleted_count=result.deleted_count,
            message=f'Deleted {result.deleted_count} transaction(s)'
        )

    except PyMongoError as e:
        current_app.logger.error(f"Database error bulk deleting transactions: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to delete transactions', 500)
