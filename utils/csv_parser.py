"""
CSV Parser Utility
Flexible CSV parsing with auto-format detection.
"""
import csv
import io
from datetime import datetime
from dateutil import parser as date_parser


class CSVParser:
    """
    Flexible CSV parser that auto-detects date formats and column structure.
    """

    # Common date format patterns
    DATE_FORMATS = [
        '%Y-%m-%d',      # 2024-12-19
        '%m/%d/%Y',      # 12/19/2024
        '%d/%m/%Y',      # 19/12/2024
        '%Y/%m/%d',      # 2024/12/19
        '%m-%d-%Y',      # 12-19-2024
        '%d-%m-%Y',      # 19-12-2024
        '%b %d, %Y',     # Dec 19, 2024
        '%B %d, %Y',     # December 19, 2024
        '%d %b %Y',      # 19 Dec 2024
        '%d %B %Y',      # 19 December 2024
    ]

    # Common column name variations
    DATE_COLUMNS = ['date', 'transaction date', 'trans date', 'posted date', 'posting date']
    DESCRIPTION_COLUMNS = ['description', 'merchant', 'memo', 'transaction', 'payee', 'details',
                           'description 1']  # Canadian banks use "Description 1"
    AMOUNT_COLUMNS = ['amount', 'debit', 'credit', 'transaction amount', 'value',
                      'cad$', 'usd$']  # Canadian banks use currency-specific columns

    @staticmethod
    def detect_date_format(date_string):
        """
        Detect the date format by trying common patterns.

        Args:
            date_string: Date string to parse

        Returns:
            datetime object

        Raises:
            ValueError: If date cannot be parsed
        """
        # Try dateutil parser first (handles most formats)
        try:
            return date_parser.parse(date_string, fuzzy=False)
        except (ValueError, TypeError, OverflowError):
            pass

        # Try specific formats
        for fmt in CSVParser.DATE_FORMATS:
            try:
                return datetime.strptime(date_string.strip(), fmt)
            except ValueError:
                continue

        raise ValueError(f"Could not parse date: {date_string}")

    @staticmethod
    def find_column(headers, possible_names):
        """
        Find a column by checking possible name variations.

        Args:
            headers: List of column headers
            possible_names: List of possible column names

        Returns:
            Column name if found, None otherwise
        """
        headers_lower = [h.lower().strip() for h in headers]

        for possible_name in possible_names:
            if possible_name in headers_lower:
                idx = headers_lower.index(possible_name)
                return headers[idx]

        return None

    @staticmethod
    def parse_amount(amount_string):
        """
        Parse amount string to float.
        Handles various formats: $1,234.56, (123.45), -123.45, etc.

        Args:
            amount_string: Amount string to parse

        Returns:
            float: Parsed amount (negative for expenses, positive for income)
        """
        if isinstance(amount_string, (int, float)):
            return float(amount_string)

        # Convert to string and clean up
        amount_str = str(amount_string).strip()

        # Handle empty or null values
        if not amount_str or amount_str.lower() in ['', 'null', 'none', 'n/a']:
            return 0.0

        # Check if wrapped in parentheses (accounting format for negative)
        is_negative = False
        if amount_str.startswith('(') and amount_str.endswith(')'):
            is_negative = True
            amount_str = amount_str[1:-1]

        # Remove currency symbols and commas
        amount_str = amount_str.replace('$', '').replace(',', '').replace(' ', '')

        # Handle negative sign
        if amount_str.startswith('-'):
            is_negative = True
            amount_str = amount_str[1:]

        try:
            amount = float(amount_str)
            return -abs(amount) if is_negative else amount
        except ValueError as e:
            raise ValueError(f"Could not parse amount: {amount_string}") from e

    @staticmethod
    def detect_columns(headers):
        """
        Auto-detect date, description, and amount columns.

        Args:
            headers: List of CSV column headers

        Returns:
            dict: Mapping of 'date', 'description', 'amount' to actual column names

        Raises:
            ValueError: If required columns cannot be detected
        """
        mapping = {}

        # Find date column
        date_col = CSVParser.find_column(headers, CSVParser.DATE_COLUMNS)
        if not date_col:
            raise ValueError(f"Could not find date column. Available columns: {headers}")
        mapping['date'] = date_col

        # Find description column
        desc_col = CSVParser.find_column(headers, CSVParser.DESCRIPTION_COLUMNS)
        if not desc_col:
            raise ValueError(f"Could not find description column. Available columns: {headers}")
        mapping['description'] = desc_col

        # Find amount column(s) - some banks have multiple currency columns (CAD$, USD$)
        headers_lower = [h.lower().strip() for h in headers]
        amount_cols = []
        for possible_name in CSVParser.AMOUNT_COLUMNS:
            if possible_name in headers_lower:
                idx = headers_lower.index(possible_name)
                amount_cols.append(headers[idx])

        if not amount_cols:
            raise ValueError(f"Could not find amount column. Available columns: {headers}")

        # If only one amount column, use it directly. If multiple, store all
        mapping['amount'] = amount_cols[0] if len(amount_cols) == 1 else None
        mapping['amount_columns'] = amount_cols if len(amount_cols) > 1 else None

        return mapping

    @staticmethod
    def _parse_row(row, column_mapping):
        """
        Parse a single CSV row into a transaction dict.

        Args:
            row: CSV row dict
            column_mapping: Column name mapping

        Returns:
            dict: Transaction data or None if row is empty

        Raises:
            ValueError: If row data is invalid
        """
        date_str = row[column_mapping['date']]
        description = row[column_mapping['description']]

        # Handle multiple amount columns (e.g., CAD$, USD$ in Canadian banks)
        if column_mapping.get('amount_columns'):
            # Find first non-empty amount from multiple columns
            amount_str = None
            for col in column_mapping['amount_columns']:
                value = row.get(col, '').strip()
                if value:
                    amount_str = value
                    break
            if not amount_str:
                amount_str = ''
        else:
            # Single amount column
            amount_str = row[column_mapping['amount']]

        # Skip empty rows
        if not date_str and not description and not amount_str:
            return None

        return {
            'date': CSVParser.detect_date_format(date_str),
            'description': description.strip(),
            'amount': CSVParser.parse_amount(amount_str)
        }

    @staticmethod
    def parse_csv(file_content, filename=None):
        """
        Parse CSV file with auto-detection of format.

        Args:
            file_content: File content (string or bytes)
            filename: Optional filename for reference

        Returns:
            dict: {
                'transactions': List of transaction dicts,
                'filename': Original filename,
                'row_count': Number of rows parsed,
                'errors': List of error messages for skipped rows
            }
        """
        # Convert bytes to string if needed
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8')

        # Parse CSV and detect columns
        reader = csv.DictReader(io.StringIO(file_content))
        if not reader.fieldnames:
            raise ValueError("CSV file is empty or has no headers")

        column_mapping = CSVParser.detect_columns(reader.fieldnames)

        # Parse rows
        transactions = []
        errors = []
        row_num = 1

        for row in reader:
            row_num += 1
            try:
                transaction = CSVParser._parse_row(row, column_mapping)
                if transaction:
                    transactions.append(transaction)
            except (ValueError, KeyError, IndexError, TypeError) as e:
                errors.append(f"Row {row_num}: {str(e)}")

        return {
            'transactions': transactions,
            'filename': filename or 'unknown.csv',
            'row_count': len(transactions),
            'errors': errors,
            'column_mapping': column_mapping
        }

    @staticmethod
    def validate_csv(file_content):
        """
        Validate CSV file without parsing all rows.
        Quick check to see if file is valid.

        Args:
            file_content: File content (string or bytes)

        Returns:
            dict: {
                'valid': bool,
                'headers': List of column names,
                'error': Error message if invalid
            }
        """
        try:
            # Convert bytes to string if needed
            if isinstance(file_content, bytes):
                file_content = file_content.decode('utf-8')

            # Parse CSV headers
            csv_file = io.StringIO(file_content)
            reader = csv.DictReader(csv_file)

            headers = reader.fieldnames
            if not headers:
                return {
                    'valid': False,
                    'headers': [],
                    'error': 'CSV file is empty or has no headers'
                }

            # Try to detect columns
            try:
                column_mapping = CSVParser.detect_columns(headers)
            except ValueError as e:
                return {
                    'valid': False,
                    'headers': headers,
                    'error': str(e)
                }

            return {
                'valid': True,
                'headers': headers,
                'column_mapping': column_mapping
            }

        except (ValueError, UnicodeDecodeError, KeyError) as e:
            return {
                'valid': False,
                'headers': [],
                'error': str(e)
            }
