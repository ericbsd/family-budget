"""
Transaction model.
Handles transaction data validation and helper methods.
"""
from datetime import datetime, UTC


class Transaction:
    """
    Transaction model for budget tracking.

    Schema:
        date: datetime - Transaction date
        description: str - Transaction description (merchant name)
        amount: float - Transaction amount (negative for expenses, positive for income)
        category_id: int - Category ID (reference to categories.id)
        source_file: str - Original CSV filename
        upload_date: datetime - When transaction was uploaded
        notes: str - Optional user notes
        auto_categorized: bool - True if assigned by system
        confidence: float - Confidence score for auto-categorization (0.0-1.0)
    """

    @staticmethod
    def create(date: str | datetime, description: str, amount: float, **optional) -> dict:
        """
        Create a new transaction document.

        Args:
            date: Transaction date as datetime or YYYY-MM-DD string
            description: Transaction description
            amount: Transaction amount
            **optional: Optional fields:
                category_id: int - Category ID (default 0 = Uncategorized)
                source_file: str - Source CSV filename (default None)
                notes: str - Optional notes (default '')
                auto_categorized: bool - Whether auto-categorized (default False)
                confidence: float - Confidence score 0.0-1.0 (default 0.0)

        Returns:
            dict: Transaction document ready for MongoDB insertion

        Raises:
            ValueError: If date, amount, category_id, or confidence are invalid
        """
        category_id = optional.get('category_id', 0)
        account_id = optional.get('account_id', None)
        source_file = optional.get('source_file', None)
        notes = optional.get('notes', '')
        auto_categorized = optional.get('auto_categorized', False)
        confidence = optional.get('confidence', 0.0)

        if isinstance(date, str):
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                try:
                    date = datetime.strptime(date, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"Could not parse date: {date}")

        try:
            amount = float(amount)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid amount: {amount}") from exc

        if not isinstance(category_id, int) or category_id < 0:
            raise ValueError(f"category_id must be a non-negative integer, got {category_id}")

        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {confidence}")

        return {
            'date': date,
            'description': str(description).strip(),
            'amount': amount,
            'category_id': category_id,
            'account_id': account_id,
            'source_file': source_file,
            'upload_date': datetime.now(UTC),
            'notes': str(notes).strip(),
            'auto_categorized': bool(auto_categorized),
            'confidence': float(confidence),
        }

    @staticmethod
    def validate(transaction: dict) -> bool:
        """
        Validate a transaction document has all required fields with correct types.

        Args:
            transaction: Transaction document to validate

        Returns:
            bool: True if valid

        Raises:
            ValueError: If any field is missing or invalid
        """
        required_fields = [
            'date',
            'description',
            'amount',
            'category_id',
        ]

        for field in required_fields:
            if field not in transaction:
                raise ValueError(f"Missing required field: {field}")

        if not isinstance(transaction['date'], datetime):
            raise ValueError("date must be a datetime object")

        if not isinstance(transaction['amount'], (int, float)):
            raise ValueError("amount must be a number")

        if not isinstance(transaction['category_id'], int) or transaction['category_id'] < 0:
            raise ValueError("category_id must be a non-negative integer")

        if 'confidence' in transaction:
            if not 0.0 <= transaction['confidence'] <= 1.0:
                raise ValueError("confidence must be between 0.0 and 1.0")

        return True

    @staticmethod
    def to_json(transaction: dict) -> dict:
        """
        Convert transaction to JSON-serializable format.

        Args:
            transaction: Transaction document from MongoDB

        Returns:
            dict: JSON-serializable transaction
        """
        result = transaction.copy()

        if '_id' in result:
            result['_id'] = str(result['_id'])

        if 'date' in result and isinstance(result['date'], datetime):
            result['date'] = result['date'].isoformat()

        if 'upload_date' in result and isinstance(result['upload_date'], datetime):
            result['upload_date'] = result['upload_date'].isoformat()

        return result

    @staticmethod
    def from_csv_row(row: dict, source_file: str) -> dict:
        """
        Create transaction from CSV row.

        Args:
            row: CSV row data with 'date', 'description', 'amount' keys
            source_file: Source filename

        Returns:
            dict: Transaction document
        """
        return Transaction.create(
            date=row['date'],
            description=row['description'],
            amount=row['amount'],
            category_id=0,
            source_file=source_file,
            auto_categorized=False,
            confidence=0.0,
        )
