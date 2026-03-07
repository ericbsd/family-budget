"""
Auto-Categorization Utility
Smart categorization system that learns merchant patterns.
"""
import re
from datetime import datetime, UTC
from fuzzywuzzy import fuzz


class AutoCategorizer:
    """
    Auto-categorization system using pattern matching and learning.
    """

    # Generic bank prefixes that precede the actual merchant name.
    # These are stripped before extracting the merchant pattern.
    GENERIC_PREFIXES = [
        r'CONTACTLESS INTERAC PURCHASE\s*-?\s*',
        r'INTERAC PURCHASE\s*-?\s*',
        r'ONLINE BANKING TRANSFER\s*-?\s*',
        r'E-TRANSFER\s+(?:SENT|RECEIVED)\s*',
        r'INTERNET BANKING\s*-?\s*',
        r'POS PURCHASE\s*-?\s*',
        r'VISA PURCHASE\s*-?\s*',
        r'DEBIT PURCHASE\s*-?\s*',
        r'POINT OF SALE\s*-?\s*',
        r'ATM\s+(?:WITHDRAWAL|DEPOSIT)\s*-?\s*',
    ]

    def __init__(self, mongo):
        """
        Initialize auto-categorizer with a MongoDB connection.

        Args:
            mongo: Flask-PyMongo instance
        """
        self.mongo = mongo

    ENTRY_CATEGORY_ID = 1   # Money coming in (default)
    SAVINGS_CATEGORY_ID = 16  # Savings account deposits

    def categorize(self, description, amount=None, account_type=None):
        """
        Auto-categorize a transaction based on description and amount.

        Args:
            description: Transaction description
            amount: Transaction amount (positive = income, negative = expense)

        Returns:
            dict: {
                'category_id': Category ID (int),
                'confidence': Confidence score (0.0-1.0),
                'match_type': Type of match used (exact/contains/fuzzy/amount/none)
            }
        """
        description_clean = description.strip().upper()

        if result := self._exact_match(description_clean):
            return result

        if result := self._contains_match(description_clean):
            return result

        if result := self._fuzzy_match(description_clean):
            return result

        # Positive amount with no rule match → Entry or Savings
        if amount is not None and amount > 0:
            cat_id = self.SAVINGS_CATEGORY_ID if account_type == 'savings' else self.ENTRY_CATEGORY_ID
            return {
                'category_id': cat_id,
                'confidence': 1.0,
                'match_type': 'amount'
            }

        # No match found - return Uncategorized (ID 0)
        return {
            'category_id': 0,
            'confidence': 0.0,
            'match_type': 'none'
        }

    def _exact_match(self, description):
        """
        Try the exact description match from categorization rules.

        Args:
            description: Cleaned transaction description

        Returns:
            dict or None: Match result if found
        """
        if rule := self.mongo.db.categorization_rules.find_one(
            {'pattern': description, 'match_type': 'exact'}
        ):
            # Update rule usage
            self._update_rule_usage(rule['_id'])

            return {
                'category_id': rule['category_id'],
                'confidence': 1.0,
                'match_type': 'exact'
            }

        return None

    def _contains_match(self, description):
        """
        Try pattern matching using 'contains' rules.

        Args:
            description: Cleaned transaction description

        Returns:
            dict or None: Match result if found
        """
        # Get all 'contains' rules
        rules = self.mongo.db.categorization_rules.find({
            'match_type': 'contains'
        }).sort('use_count', -1)  # Prioritize frequently used rules

        for rule in rules:
            pattern = rule['pattern'].upper()
            if pattern in description:
                # Update rule usage
                self._update_rule_usage(rule['_id'])

                return {
                    'category_id': rule['category_id'],
                    'confidence': 0.9,
                    'match_type': 'contains'
                }

        return None

    def _fuzzy_match(self, description):
        """
        Try fuzzy string matching against known patterns.

        Args:
            description: Cleaned transaction description

        Returns:
            dict or None: Match result if found
        """
        # Get all fuzzy rules
        rules = self.mongo.db.categorization_rules.find({
            'match_type': 'fuzzy'
        })

        best_match = None
        best_score = 0
        best_rule = None

        for rule in rules:
            pattern = rule['pattern'].upper()
            score = fuzz.ratio(pattern, description)

            if score > best_score:
                best_score = score
                best_match = rule['category_id']
                best_rule = rule

        # Only accept fuzzy matches with score >= 80
        if best_score >= 80:
            # Update rule usage
            self._update_rule_usage(best_rule['_id'])

            confidence = best_score / 100.0

            return {
                'category_id': best_match,
                'confidence': confidence,
                'match_type': 'fuzzy'
            }

        return None

    def _update_rule_usage(self, rule_id):
        """
        Update rule usage statistics.

        Args:
            rule_id: Rule ObjectId
        """
        self.mongo.db.categorization_rules.update_one(
            {'_id': rule_id},
            {
                '$set': {'last_used': datetime.now(UTC)},
                '$inc': {'use_count': 1}
            }
        )

    def learn_from_categorization(self, description, category_id):
        """
        Learn from manual categorization by creating or updating rules.

        Args:
            description: Transaction description
            category_id: Assigned category ID (int)

        Returns:
            dict: Created/updated rule
        """
        description_clean = description.strip().upper()

        # Extract merchant name (remove numbers, locations, etc.)
        merchant_pattern = self._extract_merchant_pattern(description_clean)

        if existing_rule := self.mongo.db.categorization_rules.find_one(
            {'pattern': merchant_pattern, 'match_type': 'contains'}
        ):
            # Update existing rule's category_id if different
            if existing_rule['category_id'] != category_id:
                self.mongo.db.categorization_rules.update_one(
                    {'_id': existing_rule['_id']},
                    {
                        '$set': {
                            'category_id': category_id,
                            'last_used': datetime.now(UTC)
                        },
                        '$inc': {'use_count': 1}
                    }
                )

            return existing_rule

        # Create new rule
        rule = {
            'pattern': merchant_pattern,
            'category_id': category_id,
            'match_type': 'contains',
            'created_date': datetime.now(UTC),
            'last_used': datetime.now(UTC),
            'use_count': 1
        }

        result = self.mongo.db.categorization_rules.insert_one(rule)
        rule['_id'] = result.inserted_id

        return rule

    def batch_categorize_similar(self, description, category_id):
        """
        Find and categorize all uncategorized transactions with similar descriptions.
        This provides immediate value when a user manually categorizes a transaction.

        Args:
            description: Transaction description to match
            category_id: Category ID to assign

        Returns:
            int: Number of transactions updated
        """
        description_clean = description.strip().upper()
        merchant_pattern = self._extract_merchant_pattern(description_clean)

        # Build an anchor from words that appear BEFORE the merchant name in the
        # original description (i.e. the bank prefix words). This prevents
        # cross-type false positives ("E-TRANSFER SENT" never matches
        # "CONTACTLESS INTERAC PURCHASE") without the overlap bug that occurs
        # when a merchant word also appears inside the first-3-words anchor.
        merchant_words = set(merchant_pattern.split())
        anchor_words = []
        for word in description_clean.split():
            if word in merchant_words:
                break
            anchor_words.append(word)

        if anchor_words:
            anchor = re.escape(' '.join(anchor_words[:3]))
            batch_regex = f'^{anchor}.*{re.escape(merchant_pattern)}'
        else:
            # No prefix — merchant starts the description, match anywhere
            batch_regex = re.escape(merchant_pattern)

        # Find all uncategorized transactions (category_id=0) that match the pattern
        uncategorized = self.mongo.db.transactions.find({
            'category_id': 0,
            'description': {'$regex': batch_regex, '$options': 'i'}
        })

        # Count and collect IDs
        transaction_ids = [txn['_id'] for txn in uncategorized]

        if not transaction_ids:
            return 0

        # Bulk update all matching transactions
        result = self.mongo.db.transactions.update_many(
            {'_id': {'$in': transaction_ids}},
            {
                '$set': {
                    'category_id': category_id,
                    'auto_categorized': True,
                    'confidence': 0.9  # High confidence for pattern match
                }
            }
        )

        return result.modified_count

    def _extract_merchant_pattern(self, description):
        """
        Extract merchant name from transaction description.
        Removes store numbers, locations, dates, etc.

        Args:
            description: Transaction description

        Returns:
            str: Extracted merchant pattern
        """
        # Strip known generic bank prefixes (e.g. "CONTACTLESS INTERAC PURCHASE - ")
        # so the first words are the actual merchant, not the bank transaction type.
        pattern = description
        for prefix in self.GENERIC_PREFIXES:
            stripped = re.sub(f'^{prefix}', '', pattern, flags=re.IGNORECASE).strip()
            if stripped != pattern:
                pattern = stripped
                break

        # Remove leading transaction codes (e.g. "2024", "8276", "6736")
        # — standalone 3-6 digit numbers that appear before the merchant name
        pattern = re.sub(r'^\d{3,6}\s+', '', pattern)

        # Remove store/terminal numbers (#123, #456; also trailing bare #)
        pattern = re.sub(r'#\d*', '', pattern)

        # Remove dates in various formats
        pattern = re.sub(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', '', pattern)

        # Remove trailing bank reference codes (mixed letters+digits, e.g. WWM4AK, RMEEU7, 82ZAEA)
        pattern = re.sub(r'\s+(?:[A-Z]+\d[A-Z0-9]*|\d+[A-Z][A-Z0-9]*)\s*$', '', pattern)

        # Remove standalone trailing numbers
        pattern = re.sub(r'\s+\d+\s*$', '', pattern)

        # Remove extra whitespace and punctuation left at boundaries
        pattern = pattern.strip(' -/')
        pattern = ' '.join(pattern.split())

        # Take first 4 significant words (the merchant name)
        words = pattern.split()
        if len(words) > 4:
            pattern = ' '.join(words[:4])

        # If extraction left us with something meaningless (empty or pure digits),
        # fall back to the first 3 words of the original description.
        if not pattern or pattern.isdigit() or len(pattern) < 3:
            fallback_words = description.split()
            pattern = ' '.join(fallback_words[:3])

        return pattern.strip()

    def get_categorization_stats(self):
        """
        Get statistics about categorization rules.

        Returns:
            dict: Statistics
        """
        total_rules = self.mongo.db.categorization_rules.count_documents({})

        rules_by_type = {}
        for match_type in ['exact', 'contains', 'fuzzy', 'regex']:
            count = self.mongo.db.categorization_rules.count_documents({
                'match_type': match_type
            })
            rules_by_type[match_type] = count

        # Most used rules
        most_used = list(
            self.mongo.db.categorization_rules
            .find()
            .sort('use_count', -1)
            .limit(10)
        )

        return {
            'total_rules': total_rules,
            'rules_by_type': rules_by_type,
            'most_used_rules': [
                {
                    'pattern': rule['pattern'],
                    'category_id': rule['category_id'],
                    'use_count': rule['use_count']
                }
                for rule in most_used
            ]
        }
