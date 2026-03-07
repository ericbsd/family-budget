"""
Account model.
Handles account data validation and helper methods.
"""
from datetime import datetime, UTC

from utils.responses import doc_to_json

VALID_TYPES = (
    'checking',
    'savings',
    'credit_card',
    'loan',
    'mortgage',
    'investment',
)
VALID_CURRENCIES = ('CAD', 'USD')

TYPE_LABELS = {
    'checking': 'Chequing',
    'savings': 'Savings',
    'credit_card': 'Credit Card',
    'loan': 'Loan',
    'mortgage': 'Mortgage',
    'investment': 'Investment',
}


class Account:
    """
    Account model for bank and financial accounts.

    Schema:
        id: int - Auto-incrementing account ID
        name: str - Account name (e.g. "TD Chequing")
        type: str - Account type (checking/savings/credit_card/loan/mortgage/investment)
        institution: str - Bank or institution name (optional)
        color: str - Hex color code for UI display
        currency: str - CAD or USD
        is_active: bool - Whether the account is active
        created_date: datetime - When the account was created
    """

    @staticmethod
    def get_next_id(mongo) -> int:
        """
        Get the next auto-incrementing ID for a new account.

        Args:
            mongo: Flask-PyMongo instance

        Returns:
            int: Next available account ID
        """
        highest = mongo.db.accounts.find_one(sort=[('id', -1)])
        if highest and 'id' in highest:
            return highest['id'] + 1
        return 1

    @staticmethod
    def create(
        account_id: int,
        name: str,
        type_: str,
        institution: str = '',
        color: str = '#42A5F5',
        currency: str = 'CAD',
    ) -> dict:
        """
        Create a new account document.

        Args:
            account_id: Account ID (use get_next_id() to generate)
            name: Account name
            type_: Account type (must be one of VALID_TYPES)
            institution: Bank or institution name (optional)
            color: Hex color code for UI display
            currency: Currency code (CAD or USD, defaults to CAD)

        Returns:
            dict: Account document ready for MongoDB insertion

        Raises:
            ValueError: If type_ is not a valid account type
        """
        if type_ not in VALID_TYPES:
            raise ValueError(f"Invalid type '{type_}'. Must be one of: {', '.join(VALID_TYPES)}")
        if currency not in VALID_CURRENCIES:
            currency = 'CAD'
        return {
            'id': account_id,
            'name': str(name).strip(),
            'type': type_,
            'institution': str(institution).strip(),
            'color': str(color),
            'currency': currency,
            'is_active': True,
            'created_date': datetime.now(UTC),
        }

    @staticmethod
    def transaction_count(account_id: int, mongo) -> int:
        """
        Return the number of transactions associated with an account.

        Args:
            account_id: The account ID to check.
            mongo: Flask-PyMongo instance.

        Returns:
            int: Number of transactions referencing this account.
        """
        return mongo.db.transactions.count_documents({'account_id': account_id})

    @staticmethod
    def to_json(doc: dict) -> dict:
        """
        Convert account document to JSON-serializable format.

        Args:
            doc: Account document from MongoDB

        Returns:
            dict: JSON-serializable account
        """
        return doc_to_json(doc)
