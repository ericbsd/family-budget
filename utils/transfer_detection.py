"""
Transfer detection utility.
Finds pairs of transactions across different accounts that represent the
same real-world transfer and tags both legs as the system Transaction
category so they are excluded from spending views.
"""
from pymongo import UpdateOne

from utils.categorization import AutoCategorizer

TRANSACTION_CATEGORY_ID = 2
TRANSFER_WINDOW_DAYS = 3
TRANSFER_CANDIDATE_CATEGORY_IDS = {0, 1, 16, 17}
NON_TRANSFER_ACCOUNT_TYPES = {'mortgage'}
PURCHASE_ACCOUNT_TYPES = {'credit_card'}


def _group_by_amount(candidates: list, accounts: dict) -> dict:
    """
    Bucket candidate transactions by their account currency and absolute amount.

    Transactions on a non-transfer account type (e.g. mortgage) and
    withdrawals on a purchase account type (e.g. credit card) are left out
    of every bucket since they must never be tagged as a transfer.

    Args:
        candidates: Transaction documents eligible for transfer matching.
        accounts: Mapping of account_id to account document.

    Returns:
        dict: A (currency, absolute amount rounded to cents) key mapped to a
            list of transactions sharing that currency and amount.
    """
    groups: dict = {}
    for transaction in candidates:
        account = accounts.get(transaction['account_id'], {})
        account_type = account.get('type')
        if account_type in NON_TRANSFER_ACCOUNT_TYPES:
            continue
        if account_type in PURCHASE_ACCOUNT_TYPES and transaction['amount'] < 0:
            continue
        key = (account.get('currency', 'CAD'), round(abs(transaction['amount']), 2))
        groups.setdefault(key, []).append(transaction)
    return groups


def _find_partner(transaction: dict, group: list, matched_ids: set) -> dict | None:
    """
    Find the first unmatched transaction in a group that pairs with the given one.

    A partner must belong to a different account, carry the opposite sign,
    and fall within TRANSFER_WINDOW_DAYS of the given transaction's date.

    Args:
        transaction: The transaction looking for a partner.
        group: Other transactions sharing the same absolute amount.
        matched_ids: IDs already claimed by an earlier pairing in this run.

    Returns:
        dict or None: The matching partner transaction, if found.
    """
    for candidate in group:
        if candidate['_id'] in matched_ids or candidate['_id'] == transaction['_id']:
            continue
        if candidate['account_id'] == transaction['account_id']:
            continue
        if (candidate['amount'] > 0) == (transaction['amount'] > 0):
            continue
        if abs((candidate['date'] - transaction['date']).days) > TRANSFER_WINDOW_DAYS:
            continue
        return candidate
    return None


def detect_transfers(mongo) -> int:
    """
    Scan transactions for inter-account transfer pairs and tag them.

    A pair is treated as a transfer when both legs belong to different
    accounts, carry opposite-sign amounts of the same magnitude, and fall
    within a few days of each other. Only transactions that are uncategorized
    or still auto-categorized are considered, so a transaction the user has
    manually categorized is never overridden. Mortgage accounts are excluded
    entirely since mortgage payments always count as spending.

    Args:
        mongo: Flask-PyMongo instance.

    Returns:
        int: Number of transfer pairs tagged in this run.
    """
    accounts = {
        account['id']: account
        for account in mongo.db.accounts.find()
    }

    candidates = list(mongo.db.transactions.find({
        'category_id': {'$in': list(TRANSFER_CANDIDATE_CATEGORY_IDS)},
        '$or': [
            {'category_id': 0},
            {'auto_categorized': True},
        ],
        'account_id': {'$ne': None},
    }).sort('date', 1))

    groups = _group_by_amount(candidates, accounts)

    matched_ids: set = set()
    updates = []
    for group in groups.values():
        for transaction in group:
            if transaction['_id'] in matched_ids:
                continue
            if partner := _find_partner(transaction, group, matched_ids):
                matched_ids.add(transaction['_id'])
                matched_ids.add(partner['_id'])
                updates.append(_tag_as_transfer(transaction['_id'], partner['_id']))
                updates.append(_tag_as_transfer(partner['_id'], transaction['_id']))

    if updates:
        mongo.db.transactions.bulk_write(updates)

    return len(updates) // 2


def _tag_as_transfer(transaction_id, partner_id) -> UpdateOne:
    """
    Build an update that tags one leg of a transfer and links it to its partner.

    Args:
        transaction_id: The ObjectId of the leg to tag.
        partner_id: The ObjectId of the other leg of the same transfer.

    Returns:
        UpdateOne: The bulk write operation for this leg.
    """
    return UpdateOne(
        {'_id': transaction_id},
        {
            '$set': {
                'category_id': TRANSACTION_CATEGORY_ID,
                'auto_categorized': True,
                'confidence': 1.0,
                'transfer_partner_id': partner_id,
            }
        },
    )


def release_transfer_partner(mongo, transaction: dict) -> None:
    """
    Unlink a transfer leg from its partner and re-categorize the partner.

    Called when one leg is recategorized or deleted, so the other leg does
    not stay tagged as a transfer on its own.

    Args:
        mongo: Flask-PyMongo instance.
        transaction: The transaction document as it was before the change.
    """
    partner_id = transaction.get('transfer_partner_id')
    if not partner_id:
        return
    mongo.db.transactions.update_one(
        {'_id': transaction['_id']},
        {'$unset': {'transfer_partner_id': ''}},
    )
    partner = mongo.db.transactions.find_one({'_id': partner_id})
    if not partner or partner.get('category_id') != TRANSACTION_CATEGORY_ID:
        return
    account = mongo.db.accounts.find_one({'id': partner.get('account_id')})
    result = AutoCategorizer(mongo).categorize(
        partner['description'],
        partner['amount'],
        account_type=account['type'] if account else None,
    )
    mongo.db.transactions.update_one(
        {'_id': partner_id},
        {
            '$set': {
                'category_id': result['category_id'],
                'auto_categorized': result['category_id'] != 0,
                'confidence': result['confidence'],
            },
            '$unset': {'transfer_partner_id': ''},
        },
    )
