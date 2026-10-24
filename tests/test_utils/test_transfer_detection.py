"""
Tests for the transfer detection utility.
"""
from datetime import datetime

import pytest
from bson import ObjectId

from utils.db import mongo
from utils.transfer_detection import (
    TRANSACTION_CATEGORY_ID,
    _find_partner,
    _group_by_amount,
    detect_transfers,
    release_transfer_partner,
)

ACCOUNTS = [
    {'id': 2, 'name': 'Savings', 'type': 'savings'},
    {'id': 3, 'name': 'Mortgage', 'type': 'mortgage'},
    {'id': 4, 'name': 'Visa', 'type': 'credit_card'},
]


def make_transaction(account_id: int, amount: float, day: int, category_id: int = 0) -> dict:
    """
    Build a transaction document for September 2026.

    Args:
        account_id: The account the transaction belongs to.
        amount: The signed transaction amount.
        day: The day of the month.
        category_id: The category ID, Uncategorized by default.

    Returns:
        dict: A transaction document ready for insertion.
    """
    return {
        '_id': ObjectId(),
        'account_id': account_id,
        'amount': amount,
        'date': datetime(2026, 9, day),
        'category_id': category_id,
        'description': f'TRANSFER {account_id} {amount}',
    }


@pytest.mark.unit
class TestMatchingHelpers:
    """Test the grouping and pairing helpers without a database."""

    def test_group_by_amount_uses_absolute_amount(self):
        """Test that both signs of the same amount land in one group."""
        groups = _group_by_amount(
            [
                make_transaction(1, -50.0, 1),
                make_transaction(2, 50.0, 1),
            ],
            {1: 'checking', 2: 'savings'},
        )

        assert list(groups) == [50.0]
        assert len(groups[50.0]) == 2

    def test_group_by_amount_skips_mortgage(self):
        """Test that mortgage transactions are never grouped."""
        groups = _group_by_amount(
            [make_transaction(3, 1200.0, 1)],
            {3: 'mortgage'},
        )

        assert not groups

    def test_group_by_amount_skips_credit_card_purchases(self):
        """Test that credit card withdrawals are skipped but payments are kept."""
        groups = _group_by_amount(
            [
                make_transaction(4, -80.0, 1),
                make_transaction(4, 300.0, 1),
            ],
            {4: 'credit_card'},
        )

        assert list(groups) == [300.0]

    def test_find_partner_requires_opposite_sign(self):
        """Test that two withdrawals of the same amount are not paired."""
        first = make_transaction(1, -50.0, 1)
        second = make_transaction(2, -50.0, 1)

        assert _find_partner(first, [first, second], set()) is None

    def test_find_partner_requires_different_account(self):
        """Test that both legs on the same account are not paired."""
        first = make_transaction(1, -50.0, 1)
        second = make_transaction(1, 50.0, 1)

        assert _find_partner(first, [first, second], set()) is None

    def test_find_partner_respects_window(self):
        """Test that legs more than three days apart are not paired."""
        first = make_transaction(1, -50.0, 1)
        within = make_transaction(2, 50.0, 4)
        outside = make_transaction(2, 50.0, 5)

        assert _find_partner(first, [first, within], set()) is within
        assert _find_partner(first, [first, outside], set()) is None

    def test_find_partner_skips_matched(self):
        """Test that a leg already claimed by another pair is skipped."""
        first = make_transaction(1, -50.0, 1)
        second = make_transaction(2, 50.0, 1)

        assert _find_partner(first, [first, second], {second['_id']}) is None


@pytest.mark.integration
class TestDetectTransfers:
    """Test transfer detection against the test database."""

    @pytest.fixture(autouse=True)
    def _accounts(self, request, db):
        """
        Reset the test database and add accounts next to the seeded chequing.

        The client fixture drops the database, so it must run before the insert.
        """
        request.getfixturevalue('client')
        db.accounts.insert_many([dict(account) for account in ACCOUNTS])

    def test_tags_and_links_both_legs(self, db):
        """Test that a chequing to savings transfer is tagged and linked."""
        withdrawal = make_transaction(1, -50.0, 1)
        deposit = make_transaction(2, 50.0, 2, category_id=16)
        db.transactions.insert_many([withdrawal, deposit])

        assert detect_transfers(mongo) == 1

        tagged_withdrawal = db.transactions.find_one({'_id': withdrawal['_id']})
        tagged_deposit = db.transactions.find_one({'_id': deposit['_id']})
        assert tagged_withdrawal['category_id'] == TRANSACTION_CATEGORY_ID
        assert tagged_deposit['category_id'] == TRANSACTION_CATEGORY_ID
        assert tagged_withdrawal['transfer_partner_id'] == deposit['_id']
        assert tagged_deposit['transfer_partner_id'] == withdrawal['_id']

    def test_is_idempotent(self, db):
        """Test that a second run finds nothing new."""
        db.transactions.insert_many([
            make_transaction(1, -50.0, 1),
            make_transaction(2, 50.0, 1),
        ])

        assert detect_transfers(mongo) == 1
        assert detect_transfers(mongo) == 0

    def test_ignores_mortgage_payment(self, db):
        """Test that a mortgage payment stays as spending."""
        db.transactions.insert_many([
            make_transaction(1, -1200.0, 1),
            make_transaction(3, 1200.0, 1),
        ])

        assert detect_transfers(mongo) == 0

    def test_ignores_payroll_against_credit_card_purchase(self, db):
        """Test that a paycheque never pairs with a credit card purchase."""
        db.transactions.insert_many([
            make_transaction(1, 2000.0, 1, category_id=1),
            make_transaction(4, -2000.0, 2),
        ])

        assert detect_transfers(mongo) == 0

    def test_pairs_credit_card_payment(self, db):
        """Test that a credit card payment from chequing is a transfer."""
        db.transactions.insert_many([
            make_transaction(1, -300.0, 1),
            make_transaction(4, 300.0, 2, category_id=1),
        ])

        assert detect_transfers(mongo) == 1

    def test_does_not_override_manual_category(self, db):
        """Test that a manually categorized transaction is never tagged."""
        db.transactions.insert_many([
            make_transaction(1, -50.0, 1, category_id=8),
            make_transaction(2, 50.0, 1),
        ])

        assert detect_transfers(mongo) == 0

    def test_release_recategorizes_partner(self, db):
        """Test that releasing one leg unlinks and re-categorizes the other."""
        withdrawal = make_transaction(1, -50.0, 1)
        deposit = make_transaction(2, 50.0, 1, category_id=16)
        db.transactions.insert_many([withdrawal, deposit])
        detect_transfers(mongo)

        release_transfer_partner(mongo, db.transactions.find_one({'_id': withdrawal['_id']}))

        released_withdrawal = db.transactions.find_one({'_id': withdrawal['_id']})
        released_deposit = db.transactions.find_one({'_id': deposit['_id']})
        assert 'transfer_partner_id' not in released_withdrawal
        assert 'transfer_partner_id' not in released_deposit
        assert released_deposit['category_id'] == 16
