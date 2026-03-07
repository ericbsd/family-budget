"""
Accounts API Blueprint
Handles CRUD operations for bank accounts.
"""
from flask import Blueprint, request, current_app
from pymongo.errors import DuplicateKeyError, PyMongoError

from models.account import Account
from utils.db import mongo
from utils.responses import error_response, success_response

accounts_bp = Blueprint('accounts', __name__)


@accounts_bp.route('/accounts', methods=['GET'])
def list_accounts() -> tuple:
    """
    List all accounts ordered by id.

    Returns:
        JSON response with all accounts
    """
    try:
        accounts_list = list(mongo.db.accounts.find().sort('id', 1))
        return success_response(
            data=[Account.to_json(account) for account in accounts_list],
            count=len(accounts_list),
        )
    except PyMongoError as e:
        current_app.logger.error('Database error listing accounts: %s', e)
        return error_response('DATABASE_ERROR', 'Failed to retrieve accounts', 500)


@accounts_bp.route('/accounts/<int:account_id>', methods=['GET'])
def get_account(account_id: int) -> tuple:
    """
    Get a single account by ID.

    Args:
        account_id: Account ID (integer)

    Returns:
        JSON response with account data
    """
    try:
        if account := mongo.db.accounts.find_one({'id': account_id}):
            return success_response(data=Account.to_json(account))
        return error_response('NOT_FOUND', f'Account not found: {account_id}', 404)
    except PyMongoError as e:
        current_app.logger.error('Database error getting account %s: %s', account_id, e)
        return error_response('DATABASE_ERROR', 'Failed to retrieve account', 500)


@accounts_bp.route('/accounts', methods=['POST'])
def create_account() -> tuple:
    """
    Create a new account.

    Request body:
        {
            "name": "TD Chequing",
            "type": "checking",
            "institution": "TD Bank",
            "color": "#42A5F5",
            "currency": "CAD"
        }

    Returns:
        JSON response with the created account
    """
    try:
        data = request.get_json()
        if not data or not data.get('name') or not data.get('type'):
            return error_response('INVALID_REQUEST', 'name and type are required')
        next_id = Account.get_next_id(mongo)
        try:
            account = Account.create(
                next_id,
                data['name'],
                data['type'],
                data.get('institution', ''),
                data.get('color', '#42A5F5'),
                data.get('currency', 'CAD'),
            )
        except ValueError as e:
            return error_response('VALIDATION_ERROR', str(e))
        mongo.db.accounts.insert_one(account)
        return success_response(data=Account.to_json(account), status_code=201)
    except DuplicateKeyError:
        return error_response('CONFLICT', 'Account ID conflict. Please retry.', 409)
    except PyMongoError as e:
        current_app.logger.error('Database error creating account: %s', e)
        return error_response('DATABASE_ERROR', 'Failed to create account', 500)


@accounts_bp.route('/accounts/<int:account_id>', methods=['PUT'])
def update_account(account_id: int) -> tuple:
    """
    Update an existing account.
    Allowed fields: name, institution, color, currency, is_active.

    Args:
        account_id: Account ID (integer)

    Returns:
        JSON response with an updated account
    """
    try:
        data = request.get_json()
        if not data:
            return error_response('INVALID_REQUEST', 'Request body must be JSON')
        account = mongo.db.accounts.find_one({'id': account_id})
        if not account:
            return error_response('NOT_FOUND', f'Account not found: {account_id}', 404)
        allowed = {'name', 'institution', 'color', 'currency', 'is_active'}
        updates = {k: v for k, v in data.items() if k in allowed}
        if not updates:
            return error_response('NO_UPDATES', 'No valid fields to update')
        mongo.db.accounts.update_one({'id': account_id}, {'$set': updates})
        updated = mongo.db.accounts.find_one({'id': account_id})
        return success_response(data=Account.to_json(updated))
    except PyMongoError as e:
        current_app.logger.error('Database error updating account %s: %s', account_id, e)
        return error_response('DATABASE_ERROR', 'Failed to update account', 500)


@accounts_bp.route('/accounts/<int:account_id>', methods=['DELETE'])
def delete_account(account_id: int) -> tuple:
    """
    Delete an account.
    Blocked with 409 if any transaction has account_id matching this account.

    Args:
        account_id: Account ID (integer)

    Returns:
        JSON response confirming deletion
    """
    try:
        account = mongo.db.accounts.find_one({'id': account_id})
        if not account:
            return error_response('NOT_FOUND', f'Account not found: {account_id}', 404)
        if count := Account.transaction_count(account_id, mongo):
            return error_response(
                'ACCOUNT_IN_USE',
                f'Cannot delete "{account["name"]}" - used by {count} transaction(s)',
                409
            )
        mongo.db.accounts.delete_one({'id': account_id})
        return success_response(message=f'Account "{account["name"]}" deleted')
    except PyMongoError as e:
        current_app.logger.error('Database error deleting account %s: %s', account_id, e)
        return error_response('DATABASE_ERROR', 'Failed to delete account', 500)
