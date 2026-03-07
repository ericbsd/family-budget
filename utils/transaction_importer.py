"""
Transaction importer utility.
Shared logic for processing and saving parsed CSV transactions.
"""
from models.transaction import Transaction
from utils.db import mongo


def process_transactions(
    parse_result: dict,
    filename: str,
    categorizer,
    account_id: int | None = None,
    account_type: str | None = None,
) -> tuple:
    """
    Process and save transactions from parsed CSV data.

    Categorizes each transaction, creates a Transaction document, and inserts
    it into the database. Returns counts for reporting.

    Args:
        parse_result: Parsed CSV data from CSVParser.parse_csv()
        filename: The source filename for tagging each transaction
        categorizer: An AutoCategorizer instance
        account_id: The account ID to associate with each transaction
        account_type: The account type string (e.g. 'savings') used for categorization

    Returns:
        tuple: (row_count, categorized_count, uncategorized_count)
    """
    categorized_count = 0
    uncategorized_count = 0

    for row in parse_result['transactions']:
        categorization = categorizer.categorize(
            row['description'],
            row['amount'],
            account_type=account_type,
        )
        transaction = Transaction.create(
            date=row['date'],
            description=row['description'],
            amount=row['amount'],
            category_id=categorization['category_id'],
            source_file=filename,
            auto_categorized=(categorization['match_type'] != 'none'),
            confidence=categorization['confidence'],
            account_id=account_id,
        )
        mongo.db.transactions.insert_one(transaction)
        if categorization['match_type'] != 'none':
            categorized_count += 1
        else:
            uncategorized_count += 1

    return parse_result['row_count'], categorized_count, uncategorized_count
