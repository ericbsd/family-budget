"""
Aggregation Utilities
MongoDB aggregation pipelines for charts and reports.
"""
from datetime import datetime, timedelta
from calendar import monthrange


class Aggregations:
    """
    Aggregation helper class for chart data.
    """

    @staticmethod
    def get_date_range(year, month=None, quarter=None):
        """
        Get start and end dates for a period.

        Args:
            year: Year (int)
            month: Month (1-12) for monthly range
            quarter: Quarter (1-4) for quarterly range

        Returns:
            tuple: (start_date, end_date) as datetime objects
        """
        if month:
            # Monthly range
            start_date = datetime(year, month, 1)
            _, last_day = monthrange(year, month)
            end_date = datetime(year, month, last_day, 23, 59, 59)

        elif quarter:
            # Quarterly range
            quarter_months = {
                1: (1, 3),   # Q1: Jan-Mar
                2: (4, 6),   # Q2: Apr-Jun
                3: (7, 9),   # Q3: Jul-Sep
                4: (10, 12)  # Q4: Oct-Dec
            }

            if quarter not in quarter_months:
                raise ValueError(f"Invalid quarter: {quarter}. Must be 1-4")

            start_month, end_month = quarter_months[quarter]
            start_date = datetime(year, start_month, 1)
            _, last_day = monthrange(year, end_month)
            end_date = datetime(year, end_month, last_day, 23, 59, 59)

        else:
            # Annual range
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31, 23, 59, 59)

        return start_date, end_date

    @staticmethod
    def aggregate_by_category(mongo, start_date, end_date):
        """
        Aggregate spending by category for a date range.

        Args:
            mongo: Flask-PyMongo instance
            start_date: Start date (datetime)
            end_date: End date (datetime)

        Returns:
            list: Aggregated data with category, amount, count
        """
        pipeline = [
            # Filter by date range
            {
                '$match': {
                    'date': {
                        '$gte': start_date,
                        '$lte': end_date
                    }
                }
            },
            # Group by category_id
            {
                '$group': {
                    '_id': '$category_id',
                    'total': {'$sum': '$amount'},
                    'count': {'$sum': 1},
                    'avg': {'$avg': '$amount'}
                }
            },
            # Sort by total (descending)
            {
                '$sort': {'total': 1}  # 1 for ascending (most negative first)
            }
        ]

        results = list(mongo.db.transactions.aggregate(pipeline))

        # Get category details by ID from categories collection
        categories = {
            cat['id']: cat
            for cat in mongo.db.categories.find()
        }

        # Enhance results with category metadata
        enhanced_results = []
        for result in results:
            category_id = result['_id']
            category_info = categories.get(category_id, {})

            enhanced_results.append({
                'category_id': category_id,
                'category': category_info.get('name', 'Unknown'),
                'total': result['total'],
                'count': result['count'],
                'average': result['avg'],
                'color': category_info.get('color', '#9E9E9E'),
                'monthly_limit': category_info.get('monthly_limit', 0)
            })

        return enhanced_results

    @staticmethod
    def _calculate_status_and_percentage(monthly_limit, actual):
        """Helper to calculate budget status and percentage."""
        if monthly_limit > 0:
            percentage = (actual / monthly_limit) * 100
            if percentage >= 100:
                status = 'over'
            elif percentage >= 80:
                status = 'warning'
            else:
                status = 'ok'
        else:
            percentage = 0
            status = 'no_limit'
        return status, percentage

    @staticmethod
    def calculate_budget_status(mongo, year, month):
        """
        Calculate budget vs actual spending for each category.

        Args:
            mongo: Flask-PyMongo instance
            year: Year (int)
            month: Month (1-12)

        Returns:
            list: Budget status for each category
        """
        start_date, end_date = Aggregations.get_date_range(year, month=month)

        # Get actual spending by category_id
        spending_dict = {
            item['category_id']: item['total']
            for item in Aggregations.aggregate_by_category(mongo, start_date, end_date)
        }

        budget_status = []
        for category in mongo.db.categories.find():
            monthly_limit = category.get('monthly_limit', 0)
            actual = abs(spending_dict.get(category['id'], 0))
            status, percentage = Aggregations._calculate_status_and_percentage(monthly_limit, actual)

            budget_status.append({
                'category_id': category['id'],
                'category': category['name'],
                'color': category['color'],
                'budget': monthly_limit,
                'actual': actual,
                'remaining': max(0, monthly_limit - actual),
                'percentage': round(percentage, 2),
                'status': status
            })

        # Sort by percentage (over budget first)
        budget_status.sort(key=lambda x: x['percentage'], reverse=True)

        return budget_status

    @staticmethod
    def get_spending_trend(mongo, year, months=12):
        """
        Get monthly spending trend over time.

        Args:
            mongo: Flask-PyMongo instance
            year: End year
            months: Number of months to include (default: 12)

        Returns:
            list: Monthly totals
        """
        # Calculate start date
        end_date = datetime(year, 12, 31, 23, 59, 59)
        start_date = end_date - timedelta(days=months * 30)

        pipeline = [
            # Filter by date range
            {
                '$match': {
                    'date': {
                        '$gte': start_date,
                        '$lte': end_date
                    }
                }
            },
            # Extract year and month
            {
                '$project': {
                    'year': {'$year': '$date'},
                    'month': {'$month': '$date'},
                    'amount': 1
                }
            },
            # Group by year and month
            {
                '$group': {
                    '_id': {
                        'year': '$year',
                        'month': '$month'
                    },
                    'total': {'$sum': '$amount'},
                    'count': {'$sum': 1}
                }
            },
            # Sort by date
            {
                '$sort': {
                    '_id.year': 1,
                    '_id.month': 1
                }
            }
        ]

        results = list(mongo.db.transactions.aggregate(pipeline))

        # Format results
        trend_data = []
        for result in results:
            year_month = f"{result['_id']['year']}-{result['_id']['month']:02d}"
            trend_data.append({
                'month': year_month,
                'total': abs(result['total']),  # Convert to positive
                'count': result['count']
            })

        return trend_data

    @staticmethod
    def get_top_merchants(mongo, start_date, end_date, limit=10):
        """
        Get top merchants by spending for a date range.

        Args:
            mongo: Flask-PyMongo instance
            start_date: Start date (datetime)
            end_date: End date (datetime)
            limit: Number of results (default: 10)

        Returns:
            list: Top merchants by total spending
        """
        pipeline = [
            # Filter by date range
            {
                '$match': {
                    'date': {
                        '$gte': start_date,
                        '$lte': end_date
                    }
                }
            },
            # Group by description
            {
                '$group': {
                    '_id': '$description',
                    'total': {'$sum': '$amount'},
                    'count': {'$sum': 1},
                    'category_id': {'$first': '$category_id'}
                }
            },
            # Sort by total (most negative first - biggest expenses)
            {
                '$sort': {'total': 1}
            },
            # Limit results
            {
                '$limit': limit
            }
        ]

        results = list(mongo.db.transactions.aggregate(pipeline))

        # Get category details by ID
        categories = {
            cat['id']: cat['name']
            for cat in mongo.db.categories.find()
        }

        # Format results
        merchants = []
        for result in results:
            category_id = result['category_id']
            merchants.append({
                'merchant': result['_id'],
                'total': abs(result['total']),  # Convert to positive
                'count': result['count'],
                'category_id': category_id,
                'category': categories.get(category_id, 'Unknown')
            })

        return merchants

    @staticmethod
    def get_summary_stats(mongo, start_date, end_date):
        """
        Get summary statistics for a date range.

        Args:
            mongo: Flask-PyMongo instance
            start_date: Start date (datetime)
            end_date: End date (datetime)

        Returns:
            dict: Summary statistics
        """
        pipeline = [
            # Filter by date range
            {
                '$match': {
                    'date': {
                        '$gte': start_date,
                        '$lte': end_date
                    }
                }
            },
            # Separate income and expenses
            {
                '$group': {
                    '_id': None,
                    'total_expenses': {
                        '$sum': {
                            '$cond': [
                                {'$lt': ['$amount', 0]},
                                '$amount',
                                0
                            ]
                        }
                    },
                    'total_income': {
                        '$sum': {
                            '$cond': [
                                {'$gt': ['$amount', 0]},
                                '$amount',
                                0
                            ]
                        }
                    },
                    'transaction_count': {'$sum': 1},
                    'avg_transaction': {'$avg': '$amount'}
                }
            }
        ]

        results = list(mongo.db.transactions.aggregate(pipeline))

        if results:
            result = results[0]
            return {
                'total_expenses': abs(result['total_expenses']),
                'total_income': result['total_income'],
                'net': result['total_income'] + result['total_expenses'],  # expenses are negative
                'transaction_count': result['transaction_count'],
                'average_transaction': result['avg_transaction']
            }

        return {
            'total_expenses': 0,
            'total_income': 0,
            'net': 0,
            'transaction_count': 0,
            'average_transaction': 0
        }
