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
    {'id': 2, 'name': 'Savings', 'type': 'savings', 'currency': 'CAD'},
    {'id': 3, 'name': 'Mortgage', 'type': 'mortgage', 'currency': 'CAD'},
    {'id': 4, 'name': 'Visa', 'type': 'credit_card', 'currency': 'CAD'},
    {'id': 5, 'name': 'US Savings', 'type': 'savings', 'currency': 'USD'},
]


def make_transaction(
    account_id: int,
    amount: float,
    day: int,
    category_id: int = 0,
    auto_categorized: bool | None = None,
) -> dict:
    """
    Build a transaction document for September 2026.

    Args:
        account_id: The account the transaction belongs to.
        amount: The signed transaction amount.
        day: The day of the month.
        category_id: The category ID, Uncategorized by default.
        auto_categorized: Whether the category was set by the system. It
            defaults to True for any category other than Uncategorized.

    Returns:
        dict: A transaction document ready for insertion.
    """
    if auto_categorized is None:
        auto_categorized = category_id != 0
    return {
        '_id': ObjectId(),
        'account_id': account_id,
        'amount': amount,
        'date': datetime(2026, 9, day),
        'category_id': category_id,
        'auto_categorized': auto_categorized,
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
            {1: {'type': 'checking'}, 2: {'type': 'savings'}},
        )

        assert list(groups) == [('CAD', 50.0)]
        assert len(groups[('CAD', 50.0)]) == 2

    def test_group_by_amount_separates_currencies(self):
        """Test that the same amount in CAD and USD lands in different groups."""
        groups = _group_by_amount(
            [
                make_transaction(1, -50.0, 1),
                make_transaction(5, 50.0, 1),
            ],
            {1: {'type': 'checking', 'currency': 'CAD'}, 5: {'type': 'savings', 'currency': 'USD'}},
        )

        assert sorted(groups) == [('CAD', 50.0), ('USD', 50.0)]

    def test_group_by_amount_skips_mortgage(self):
        """Test that mortgage transactions are never grouped."""
        groups = _group_by_amount(
            [make_transaction(3, 1200.0, 1)],
            {3: {'type': 'mortgage'}},
        )

        assert not groups

    def test_group_by_amount_skips_credit_card_purchases(self):
        """Test that credit card withdrawals are skipped but payments are kept."""
        groups = _group_by_amount(
            [
                make_transaction(4, -80.0, 1),
                make_transaction(4, 300.0, 1),
            ],
            {4: {'type': 'credit_card'}},
        )

        assert list(groups) == [('CAD', 300.0)]

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

    def test_does_not_override_manual_savings(self, db):
        """Test that a transaction manually set to Savings is never tagged."""
        db.transactions.insert_many([
            make_transaction(1, -50.0, 1),
            make_transaction(2, 50.0, 1, category_id=16, auto_categorized=False),
        ])

        assert detect_transfers(mongo) == 0

    def test_ignores_different_currencies(self, db):
        """Test that a CAD withdrawal never pairs with a USD deposit."""
        db.transactions.insert_many([
            make_transaction(1, -50.0, 1),
            make_transaction(5, 50.0, 1, category_id=16),
        ])

        assert detect_transfers(mongo) == 0

    def test_api_serializes_and_releases_partner(self, client, db):
        """Test that the API returns linked legs and unlinks them on delete."""
        withdrawal = make_transaction(1, -50.0, 1)
        deposit = make_transaction(2, 50.0, 1, category_id=16)
        db.transactions.insert_many([withdrawal, deposit])
        detect_transfers(mongo)

        response = client.get(f"/api/transactions/{deposit['_id']}")
        assert response.status_code == 200
        assert response.get_json()['data']['transfer_partner_id'] == str(withdrawal['_id'])

        client.delete(f"/api/transactions/{withdrawal['_id']}")

        released_deposit = db.transactions.find_one({'_id': deposit['_id']})
        assert 'transfer_partner_id' not in released_deposit
        assert released_deposit['category_id'] == 16

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
